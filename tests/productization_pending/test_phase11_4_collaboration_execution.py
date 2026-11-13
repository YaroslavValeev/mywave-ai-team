# tests/test_phase11_4_collaboration_execution.py — Phase 11.4
from __future__ import annotations

import os

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.services.collaboration_action_suggestions import compute_suggestion_fingerprint, get_collaboration_action_suggestions
from app.services.collaboration_execution import (
    build_execution_from_suggestion,
    trigger_collaboration_execution,
    mark_collaboration_execution_closed,
    get_collaboration_execution,
    list_collaboration_executions,
)
from app.presenters.collaboration_execution_presenters import (
    present_collaboration_execution_card,
    format_collaboration_execution_card_telegram,
)
from app.services.owner_recommendations import get_next_actions
from app.services.action_center import execute_action_for_collaboration_execution, can_execute_action
from app.dashboard.app import app


def _exec_env(tmp_path):
    return {"COLLABORATION_EXECUTIONS_PATH": str(tmp_path / "collab_exec.json")}


# --- A. Execution shape ---
def test_collaboration_execution_shape_is_expected(db_session, tmp_path):
    with patch.dict(os.environ, _exec_env(tmp_path)):
        sug = {
            "suggestion_id": "ab12cd34",
            "suggestion_type": "owner_attention_request",
            "subject_type": "portfolio",
            "subject_key": "portfolio",
            "headline": "Test",
            "reason": "r",
            "recommended_next_step": "x",
            "safe_action_available": "open_decision_queue",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        assert ex is not None
        card = present_collaboration_execution_card(ex)
        assert card.get("execution_id", "").startswith("ce_")
        assert card.get("execution_status") == "available"
        assert "suggestion_fingerprint" in ex or ex.get("suggestion_fingerprint")


# --- B. Build from suggestion ---
def test_execution_can_be_built_from_suggestion(db_session, tmp_path):
    with patch.dict(os.environ, _exec_env(tmp_path)):
        sug = {
            "suggestion_type": "runtime_escalation",
            "subject_type": "portfolio",
            "subject_key": "portfolio",
            "headline": "Degraded",
            "reason": "runtime",
            "recommended_next_step": "check",
            "safe_action_available": "recheck_molt_health",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        e1 = build_execution_from_suggestion(sug)
        e2 = build_execution_from_suggestion(sug)
        assert e1["execution_id"] == e2["execution_id"]


# --- C. Safe action linkage ---
def test_execution_can_link_safe_action_when_available(db_session, tmp_path):
    with patch.dict(os.environ, _exec_env(tmp_path)):
        sug = {
            "suggestion_type": "approval_resolution_needed",
            "subject_type": "project",
            "subject_key": "general",
            "headline": "Approvals",
            "reason": "bottleneck",
            "safe_action_available": "open_decision_queue",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        assert ex.get("safe_action_key") == "open_decision_queue"


# --- D. Trigger and close ---
def test_trigger_and_close_collaboration_execution_work(db_session, tmp_path):
    with patch.dict(os.environ, _exec_env(tmp_path)):
        sug = {
            "suggestion_type": "x",
            "subject_type": "portfolio",
            "subject_key": "p",
            "headline": "h",
            "reason": "r",
            "safe_action_available": None,
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        eid = ex["execution_id"]
        tr = trigger_collaboration_execution(eid, actor="test", run_safe_action=False)
        assert tr.get("execution_status") in ("triggered", "in_progress")
        cl = mark_collaboration_execution_closed(eid, actor="test", reason="done")
        assert cl.get("execution_status") == "closed"


# --- E. Presenters ---
def test_collaboration_execution_presenters_are_human_readable(db_session, tmp_path):
    with patch.dict(os.environ, _exec_env(tmp_path)):
        ex = {
            "execution_id": "ce_test123",
            "execution_status": "available",
            "execution_type": "request_owner_attention",
            "execution_reason": "reason text",
            "subject_type": "portfolio",
            "subject_key": "x",
        }
        tg = format_collaboration_execution_card_telegram(ex)
        assert "ce_test123" in tg


# --- F. Routes wired ---
def test_collaboration_execution_routes_and_commands_are_wired(db_session, tmp_path):
    with patch.dict(os.environ, _exec_env(tmp_path)):
        key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/owner/collaboration/executions", headers={"X-API-Key": key})
        assert r.status_code == 200
        assert "items" in r.json()
        r2 = client.get("/owner/collaboration/executions", headers={"X-API-Key": key})
        assert r2.status_code == 200
        import app.bot.handlers as bh
        assert hasattr(bh, "handle_collaboration_executions")
        assert hasattr(bh, "handle_trigger_collaboration")


# --- G. Recommendations ---
def test_owner_recommendations_include_pending_collaboration_execution_attention(db_session, tmp_path):
    with patch.dict(os.environ, _exec_env(tmp_path)):
        sug = {
            "suggestion_type": "t",
            "subject_type": "portfolio",
            "subject_key": "p",
            "headline": "h",
            "reason": "r",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        build_execution_from_suggestion(sug)
        with patch(
            "app.services.owner_recommendations.get_degraded_signal_summary",
            return_value={"current_state": "OK", "events_count_7d": 0},
        ), patch(
            "app.services.owner_recommendations.get_blockers_summary",
            return_value={"items": [], "blockers_count": 0},
        ):
            actions = get_next_actions(limit=30)
        types = [a.get("action_type") for a in actions.get("items", [])]
        assert "pending_collaboration_execution_attention" in types


# --- H. Regression suggestions ---
def test_existing_collaboration_suggestion_features_not_broken(db_session, tmp_path):
    with patch.dict(os.environ, _exec_env(tmp_path)):
        raw = get_collaboration_action_suggestions(window_days=7, limit=5)
        assert "suggestions" in raw
        for s in raw.get("suggestions", []):
            assert "suggestion_fingerprint" in s
            assert "headline" in s


# --- I. Action center boundaries ---
def test_action_center_integration_preserves_safe_boundaries(db_session):
    assert can_execute_action("owner", "open_decision_queue") is True
    assert can_execute_action("owner", "nonexistent_action_xyz") is False
    with patch("app.services.action_center.execute_action") as m:
        m.return_value = {"success": True, "result_summary": "ok", "action_id": "a1", "status": "success"}
        execute_action_for_collaboration_execution(
            "open_decision_queue",
            role="owner",
            execution_id="ce_x",
            actor="test",
        )
        m.assert_called_once()
        call_kw = m.call_args
        assert "collaboration_execution_id" in (call_kw[1].get("context") or {})
