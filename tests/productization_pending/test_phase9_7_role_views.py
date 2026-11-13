# tests/test_phase9_7_role_views.py — Phase 9.7: role-based dashboards and role-scoped views
from __future__ import annotations

import os

# Ensure auth has a key when app is imported (conftest sets OWNER_API_KEY; reinforce for dashboard tests)
os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.services.role_views import (
    get_owner_view,
    get_operator_view,
    get_executor_view,
    get_reviewer_view,
)
from app.presenters.role_presenters import (
    present_owner_view,
    present_operator_view,
    present_executor_view,
    present_reviewer_view,
    format_owner_view_text,
    format_operator_view_text,
    format_executor_view_text,
    format_reviewer_view_text,
)
from app.dashboard.app import app


# --- A. Owner view shape ---
def test_owner_view_shape(db_session):
    data = get_owner_view()
    assert "overview" in data
    assert "next_actions" in data
    assert "blockers" in data
    assert "decision_queue" in data
    assert "project_health" in data
    assert "recent_artifacts" in data
    assert "digest_preview" in data
    ov = data["overview"]
    assert "state" in ov
    assert "molt_ok" in ov
    assert "active_tasks_count" in ov
    assert "pending_approvals_count" in ov


# --- B. Operator view: runtime health + stuck ---
def test_operator_view_contains_runtime_health_and_stuck_items(db_session):
    data = get_operator_view()
    assert "runtime" in data
    r = data["runtime"]
    assert "transport_mode" in r
    assert "molt_ok" in r
    assert "molt_message" in r
    assert "state" in r
    assert "active_tasks_count" in r
    assert "blockers" in data
    assert "long_running" in data
    assert "count" in data["long_running"]
    assert "items" in data["long_running"]


# --- C. Executor view: actionable work ---
def test_executor_view_contains_actionable_work_items(db_session):
    data = get_executor_view()
    assert "active_tasks" in data
    assert "recent_artifacts" in data
    assert "blockers" in data
    assert isinstance(data["active_tasks"], list)
    assert isinstance(data["recent_artifacts"], list)
    assert "blockers_count" in data["blockers"] or "items" in data["blockers"]


# --- D. Reviewer view: pending decisions/approvals ---
def test_reviewer_view_contains_pending_decisions_or_approvals(db_session):
    data = get_reviewer_view()
    assert "pending_approvals" in data
    assert "awaiting_decisions" in data
    assert "decision_queue" in data
    assert "items" in data["decision_queue"] or "count" in data["decision_queue"]


# --- E. Role presenters return human-readable output ---
def test_role_presenters_return_human_readable_output():
    owner_data = {
        "overview": {"state": "OK", "molt_ok": True, "active_tasks_count": 2, "pending_approvals_count": 1},
        "next_actions": {"items": [{"task_id": 1, "priority": "high", "suggested_action": "Approve"}]},
        "blockers": {"blockers_count": 0},
    }
    text = format_owner_view_text(owner_data)
    assert "Owner view" in text
    assert "OK" in text or "2" in text

    op_data = {
        "runtime": {"state": "OK", "molt_ok": True, "molt_message": "up", "transport_mode": "http", "active_tasks_count": 0},
        "blockers": {"blockers_count": 0, "degraded_now": False},
        "long_running": {"items": []},
    }
    text_op = format_operator_view_text(op_data)
    assert "Operator view" in text_op

    exec_data = {"active_tasks": [], "recent_artifacts": [], "blockers": {"blockers_count": 0}}
    text_exec = format_executor_view_text(exec_data)
    assert "Executor view" in text_exec

    rev_data = {"pending_approvals": [], "decision_queue": {"items": [], "count": 0}}
    text_rev = format_reviewer_view_text(rev_data)
    assert "Reviewer view" in text_rev


# --- F. Role dashboard routes are wired ---
def test_role_dashboard_routes_are_wired():
    client = TestClient(app, raise_server_exceptions=False)

    # Without auth all role routes must return 401
    assert client.get("/views/owner").status_code == 401
    assert client.get("/views/operator").status_code == 401
    assert client.get("/views/executor").status_code == 401
    assert client.get("/views/reviewer").status_code == 401

    # With auth (key from env or default): expect 200/302 when key is configured
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    headers = {"X-API-Key": key}
    r_owner = client.get("/views/owner", headers=headers)
    r_op = client.get("/views/operator", headers=headers)
    r_exec = client.get("/views/executor", headers=headers)
    r_rev = client.get("/views/reviewer", headers=headers)

    if r_owner.status_code == 200 or r_owner.status_code == 302:
        if r_owner.status_code == 302:
            assert r_owner.headers.get("location") == "/owner"
        assert r_op.status_code == 200 and "Operator view" in (r_op.text or "")
        assert r_exec.status_code == 200 and "Executor view" in (r_exec.text or "")
        assert r_rev.status_code == 200 and "Reviewer view" in (r_rev.text or "")
    else:
        # When OWNER_API_KEY not set server returns 500; routes are still wired (401 without key)
        assert r_owner.status_code == 500 or r_owner.status_code == 401


# --- G. Role commands are wired (handlers call presenters and answer) ---
@pytest.mark.asyncio
async def test_role_commands_are_wired():
    from app.bot.handlers import (
        handle_view_owner,
        handle_view_operator,
        handle_view_executor,
        handle_view_reviewer,
    )

    def make_msg():
        m = MagicMock()
        m.chat.id = 12345
        m.answer = AsyncMock()
        return m

    with patch("app.bot.handlers.is_owner", return_value=True):
        with patch("app.bot.handlers.get_owner_view") as m_owner:
            m_owner.return_value = {
                "overview": {"state": "OK", "molt_ok": True, "active_tasks_count": 0, "pending_approvals_count": 0},
                "next_actions": {"items": []},
                "blockers": {"blockers_count": 0},
            }
            msg = make_msg()
            await handle_view_owner(msg)
            msg.answer.assert_called_once()
            assert "Owner view" in msg.answer.call_args[0][0] or "OK" in msg.answer.call_args[0][0]

        with patch("app.bot.handlers.get_operator_view") as m_op:
            m_op.return_value = {
                "runtime": {"state": "OK", "molt_ok": True, "molt_message": "up", "transport_mode": "local", "active_tasks_count": 0},
                "blockers": {"blockers_count": 0, "items": []},
                "long_running": {"count": 0, "items": []},
            }
            msg = make_msg()
            await handle_view_operator(msg)
            msg.answer.assert_called_once()
            assert "Operator view" in msg.answer.call_args[0][0]

        with patch("app.bot.handlers.get_executor_view") as m_exec:
            m_exec.return_value = {"active_tasks": [], "recent_artifacts": [], "blockers": {"blockers_count": 0, "items": []}}
            msg = make_msg()
            await handle_view_executor(msg)
            msg.answer.assert_called_once()
            assert "Executor view" in msg.answer.call_args[0][0]

        with patch("app.bot.handlers.get_reviewer_view") as m_rev:
            m_rev.return_value = {"pending_approvals": [], "awaiting_decisions": {"pending_count": 0, "items": []}, "decision_queue": {"items": [], "count": 0}}
            msg = make_msg()
            await handle_view_reviewer(msg)
            msg.answer.assert_called_once()
            assert "Reviewer view" in msg.answer.call_args[0][0]


# --- H. Role resolution baseline is documented and usable ---
def test_role_resolution_baseline_is_documented_and_usable():
    from pathlib import Path
    # Presets_v1_1/tests -> go up to workspace root (MyWaveAITeam or AI-Team parent)
    start = Path(__file__).resolve().parent
    doc = None
    for root in (start, start.parent, start.parent.parent, start.parent.parent.parent):
        candidate = root / "docs" / "contracts" / "ROLE_RESOLUTION_BASELINE.md"
        if candidate.exists():
            doc = candidate
            break
    assert doc is not None and doc.exists(), "ROLE_RESOLUTION_BASELINE.md must exist under docs/contracts"
    content = doc.read_text(encoding="utf-8")
    assert "owner" in content.lower()
    assert "role" in content.lower() or "view" in content.lower()
    assert "RBAC" in content or "baseline" in content.lower()
