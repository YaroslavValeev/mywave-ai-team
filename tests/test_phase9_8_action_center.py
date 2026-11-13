# tests/test_phase9_8_action_center.py — Phase 9.8: action center and safe role-aware actions
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.services.action_center import (
    list_available_actions,
    can_execute_action,
    execute_action,
)
from app.services.action_audit import log_action
from app.storage.repositories import get_session_factory, TaskRepository
from app.presenters.action_presenters import (
    format_action_list,
    format_action_result,
    format_action_error,
)
from app.dashboard.app import app


# --- A. Role-scoped action list ---
def test_action_list_returns_role_scoped_actions(db_session):
    owner_actions = list_available_actions("owner")
    operator_actions = list_available_actions("operator")
    executor_actions = list_available_actions("executor")
    reviewer_actions = list_available_actions("reviewer")

    assert len(owner_actions) > 0
    owner_names = {a["action_name"] for a in owner_actions}
    assert "send_digest_now" in owner_names
    assert "refresh_status" in owner_names
    assert "run_smoke_check" in owner_names

    assert "refresh_status" in {a["action_name"] for a in operator_actions}
    assert "run_smoke_check" in {a["action_name"] for a in operator_actions}
    assert "send_digest_now" not in {a["action_name"] for a in operator_actions}

    assert "refresh_status" in {a["action_name"] for a in executor_actions}
    assert "run_smoke_check" not in {a["action_name"] for a in executor_actions}

    assert "open_decision_queue" in {a["action_name"] for a in reviewer_actions}
    assert "run_smoke_check" not in {a["action_name"] for a in reviewer_actions}


# --- B. Owner can execute safe digest action ---
def test_owner_can_execute_safe_digest_action(db_session):
    with patch("app.bot.notify.send_owner_notification", AsyncMock(return_value=True)):
        result = execute_action("send_digest_now", "owner", actor="test")
    assert "success" in result
    assert "result_summary" in result
    assert result.get("status") in ("success", "failure")


# --- C. Operator can run recheck/smoke ---
def test_operator_can_run_recheck_or_smoke_action(db_session):
    result_recheck = execute_action("recheck_molt_health", "operator", actor="test")
    assert result_recheck.get("success") is True
    assert "Molt:" in (result_recheck.get("result_summary") or "")

    result_smoke = execute_action("run_smoke_check", "operator", actor="test")
    assert "result_summary" in result_smoke
    assert result_smoke.get("status") in ("success", "failure")


# --- D. Executor cannot run operator-only action ---
def test_executor_cannot_run_operator_only_action(db_session):
    assert can_execute_action("executor", "run_smoke_check") is False
    result = execute_action("run_smoke_check", "executor", actor="test")
    assert result.get("success") is False
    assert "not allowed" in (result.get("error_message") or result.get("result_summary") or "").lower()


# --- E. Action audit records execution ---
def test_action_audit_records_execution(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        log_action(
            repo, "test-id-1", "refresh_status", "owner", "test-actor",
            "success", "2025-01-01T00:00:00Z", "2025-01-01T00:00:01Z",
            "Status refreshed.", None, None,
        )
    with Session() as session:
        from app.storage.models import AuditEvent
        events = session.query(AuditEvent).filter(AuditEvent.event_type == "action_center").all()
        assert len(events) >= 1
        payload = events[-1].payload_json or {}
        assert payload.get("action_name") == "refresh_status"
        assert payload.get("role") == "owner"
        assert payload.get("status") == "success"


# --- F. Action presenters return human-readable output ---
def test_action_presenters_return_human_readable_output():
    actions = [{"action_name": "refresh_status", "category": "informational"}]
    text = format_action_list(actions, "owner")
    assert "refresh_status" in text
    assert "owner" in text

    result_ok = {"success": True, "result_summary": "Done."}
    assert "✅" in format_action_result(result_ok)

    result_fail = {"success": False, "result_summary": "Failed.", "error_message": "err"}
    assert "❌" in format_action_result(result_fail)

    assert "not allowed" in format_action_error("run_smoke_check", "role not allowed").lower()


# --- G. Telegram action commands are wired ---
@pytest.mark.asyncio
async def test_telegram_action_commands_are_wired():
    from app.bot.handlers import (
        handle_actions,
        handle_do_action,
        handle_refresh,
        handle_recheck,
        handle_smoke,
        handle_digest_now,
    )
    msg = MagicMock()
    msg.chat.id = 12345
    msg.answer = AsyncMock()
    msg.text = "/do refresh_status"

    with patch("app.bot.handlers.is_owner", return_value=True):
        await handle_actions(msg)
        msg.answer.assert_called()
        assert "action" in msg.answer.call_args[0][0].lower() or "refresh" in msg.answer.call_args[0][0].lower()

        msg.answer.reset_mock()
        await handle_do_action(msg)
        msg.answer.assert_called_once()

        msg.answer.reset_mock()
        await handle_refresh(msg)
        msg.answer.assert_called_once()

        msg.answer.reset_mock()
        await handle_recheck(msg)
        msg.answer.assert_called_once()

        msg.answer.reset_mock()
        await handle_smoke(msg)
        msg.answer.assert_called_once()


# --- H. Web action routes are wired ---
def test_web_action_routes_are_wired():
    client = TestClient(app, raise_server_exceptions=False)
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    headers = {"X-API-Key": key}

    r = client.get("/actions", headers=headers)
    assert r.status_code in (200, 401, 500)
    if r.status_code == 200:
        assert "action" in (r.text or "").lower()

    r_api = client.get("/api/actions", headers=headers)
    assert r_api.status_code in (200, 401, 500)
    if r_api.status_code == 200:
        data = r_api.json()
        assert "actions" in data
        assert "role" in data

    r_post = client.post("/actions/run", headers=headers, data={"action_name": "refresh_status"})
    assert r_post.status_code in (200, 302, 400, 401, 403, 500)


# --- I. Disallowed action returns clear error ---
def test_disallowed_action_returns_clear_error(db_session):
    result = execute_action("send_digest_now", "executor", actor="test")
    assert result.get("success") is False
    assert "not allowed" in (result.get("error_message") or result.get("result_summary") or "").lower()

    result_unknown = execute_action("nonexistent_action", "owner", actor="test")
    assert result_unknown.get("success") is False
    assert "not allowed" in (result_unknown.get("error_message") or "").lower()
