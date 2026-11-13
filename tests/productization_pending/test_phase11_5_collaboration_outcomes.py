# tests/test_phase11_5_collaboration_outcomes.py — Phase 11.5
from __future__ import annotations

import os

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

from unittest.mock import patch
from fastapi.testclient import TestClient

import pytest

from app.services.collaboration_action_suggestions import compute_suggestion_fingerprint
from app.services.collaboration_execution import (
    build_execution_from_suggestion,
    mark_collaboration_execution_closed,
    trigger_collaboration_execution,
)
from app.services.collaboration_outcomes import (
    evaluate_collaboration_execution_outcome,
    get_collaboration_execution_outcome,
    get_collaboration_effectiveness_summary,
    get_collaboration_effectiveness_hotspots,
    list_collaboration_outcomes,
)
from app.presenters.collaboration_outcome_presenters import (
    present_collaboration_outcome_card,
    format_collaboration_outcome_card_telegram,
    present_collaboration_effectiveness_summary,
)
from app.services.owner_recommendations import get_next_actions
from app.dashboard.app import app


def _both_paths(tmp_path):
    return {
        "COLLABORATION_EXECUTIONS_PATH": str(tmp_path / "ce.json"),
        "COLLABORATION_OUTCOMES_PATH": str(tmp_path / "co.json"),
    }


def _bundle(pending=5, rework=2, degraded=False, blockers=1, proj=None):
    b = {
        "global_pending": pending,
        "global_rework": rework,
        "global_blockers": blockers,
        "degraded": degraded,
        "project_key": proj,
        "project_pending": 2 if proj else None,
        "project_rework": 1 if proj else None,
        "project_long_running": 0 if proj else None,
    }
    return b


# A. Shape
def test_collaboration_outcome_shape_is_expected(db_session, tmp_path):
    with patch.dict(os.environ, _both_paths(tmp_path)):
        sug = {
            "suggestion_type": "approval_resolution_needed",
            "subject_type": "portfolio",
            "subject_key": "portfolio",
            "headline": "x",
            "reason": "r",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        eid = ex["execution_id"]
        trigger_collaboration_execution(eid, actor="t", run_safe_action=False)
        with patch("app.services.collaboration_outcomes._capture_signal_bundle", return_value=_bundle()):
            mark_collaboration_execution_closed(eid, actor="t", reason="done")
        oc = get_collaboration_execution_outcome(eid)
        assert oc is not None
        assert oc.get("outcome_id") == f"co_{eid}"
        assert oc.get("execution_id") == eid
        assert oc.get("baseline_signal_bundle") is not None
        card = present_collaboration_outcome_card(oc)
        assert card.get("has_outcome") is True


# B. Effective when signal reduces
def test_effective_outcome_detected_when_signal_reduces(db_session, tmp_path):
    with patch.dict(os.environ, _both_paths(tmp_path)):
        sug = {
            "suggestion_type": "approval_resolution_needed",
            "subject_type": "portfolio",
            "subject_key": "portfolio",
            "headline": "x",
            "reason": "r",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        eid = ex["execution_id"]
        trigger_collaboration_execution(eid, actor="t", run_safe_action=False)

        def _snap():
            return _bundle(pending=8, rework=1)

        def _snap2():
            return _bundle(pending=2, rework=1)

        with patch("app.services.collaboration_outcomes._capture_signal_bundle", side_effect=[_snap(), _snap2()]):
            mark_collaboration_execution_closed(eid, actor="t", reason="done")
            ev = evaluate_collaboration_execution_outcome(eid, window_days=7)
        assert ev.get("outcome_status") == "improved"
        assert ev.get("effectiveness_label") == "effective"
        assert ev.get("followup_needed") is False


# C. Unchanged / follow-up
def test_unchanged_or_followup_needed_detected_when_signal_persists(db_session, tmp_path):
    with patch.dict(os.environ, _both_paths(tmp_path)):
        sug = {
            "suggestion_type": "approval_resolution_needed",
            "subject_type": "portfolio",
            "subject_key": "portfolio",
            "headline": "x",
            "reason": "r",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        eid = ex["execution_id"]
        trigger_collaboration_execution(eid, actor="t", run_safe_action=False)
        same = _bundle(pending=4, rework=2)
        with patch("app.services.collaboration_outcomes._capture_signal_bundle", return_value=same):
            mark_collaboration_execution_closed(eid, actor="t", reason="done")
            ev = evaluate_collaboration_execution_outcome(eid, window_days=7)
        assert ev.get("outcome_status") == "unchanged"
        assert ev.get("followup_needed") is True


# D. Summary explainable
def test_collaboration_effectiveness_summary_is_explainable(db_session, tmp_path):
    with patch.dict(os.environ, _both_paths(tmp_path)):
        sug = {
            "suggestion_type": "t",
            "subject_type": "portfolio",
            "subject_key": "p",
            "headline": "h",
            "reason": "r",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        eid = ex["execution_id"]
        b = _bundle()
        with patch("app.services.collaboration_outcomes._capture_signal_bundle", return_value=b):
            mark_collaboration_execution_closed(eid, actor="t", reason="done")
            evaluate_collaboration_execution_outcome(eid, window_days=7)
        s = get_collaboration_effectiveness_summary(window_days=30)
        assert s.get("explainable") is True
        assert "effective_executions_count" in s
        assert "effectiveness_by_execution_type" in s
        pres = present_collaboration_effectiveness_summary(s)
        assert pres.get("evidence_source") or pres.get("window_days") is not None
        hot = get_collaboration_effectiveness_hotspots(window_days=30, limit=5)
        assert "items" in hot


# E. Presenters
def test_collaboration_outcome_presenters_are_human_readable(db_session, tmp_path):
    raw = {
        "outcome_id": "co_ce_x",
        "execution_id": "ce_x",
        "outcome_status": "improved",
        "effectiveness_label": "effective",
        "outcome_reason": "pending 5→2",
        "followup_needed": False,
        "baseline_signal_state": "pending=5",
        "post_execution_signal_state": "pending=2",
    }
    tg = format_collaboration_outcome_card_telegram(raw)
    assert "ce_x" in tg and "effective" in tg


# F. Routes / commands wired
def test_collaboration_outcome_routes_and_commands_are_wired(db_session, tmp_path):
    with patch.dict(os.environ, _both_paths(tmp_path)):
        key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/owner/collaboration/outcomes", headers={"X-API-Key": key})
        assert r.status_code == 200
        r2 = client.get("/api/owner/collaboration/outcomes/summary", headers={"X-API-Key": key})
        assert r2.status_code == 200
        import app.bot.handlers as bh

        assert hasattr(bh, "handle_collaboration_outcomes")
        assert hasattr(bh, "handle_collaboration_followup")


# G. Recommendations
def test_owner_recommendations_include_collaboration_outcome_signals(db_session, tmp_path):
    with patch.dict(os.environ, _both_paths(tmp_path)):
        with patch(
            "app.services.collaboration_outcomes.get_followup_needed_executions",
            return_value={"count": 3, "items": [{}, {}, {}]},
        ), patch(
            "app.services.collaboration_outcomes.get_collaboration_effectiveness_summary",
            return_value={
                "ineffective_executions_count": 3,
                "effective_executions_count": 4,
            },
        ), patch(
            "app.services.collaboration_outcomes.get_collaboration_effectiveness_hotspots",
            return_value={"items": [{"count": 2, "subject_type": "project", "subject_key": "alpha", "execution_type": "x"}]},
        ), patch(
            "app.services.owner_recommendations.get_degraded_signal_summary",
            return_value={"current_state": "OK", "events_count_7d": 0},
        ), patch(
            "app.services.owner_recommendations.get_blockers_summary",
            return_value={"items": [], "blockers_count": 0},
        ):
            actions = get_next_actions(limit=40)
        types = [a.get("action_type") for a in actions.get("items", [])]
        assert "collaboration_execution_followup_signal" in types
        assert "ineffective_collaboration_pattern_signal" in types
        assert "effective_collaboration_pattern_signal" in types
        assert "project_collaboration_needs_revisit" in types


# H. Regression 11.4
def test_existing_execution_layer_not_broken(db_session, tmp_path):
    with patch.dict(os.environ, _both_paths(tmp_path)):
        sug = {
            "suggestion_type": "x",
            "subject_type": "portfolio",
            "subject_key": "p",
            "headline": "h",
            "reason": "r",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        eid = ex["execution_id"]
        trigger_collaboration_execution(eid, actor="t", run_safe_action=False)
        cl = mark_collaboration_execution_closed(eid, actor="t", reason="done")
        assert cl.get("execution_status") == "closed"
        assert cl.get("closed_at")


# I. Traceability
def test_traceability_execution_to_outcome_is_preserved(db_session, tmp_path):
    with patch.dict(os.environ, _both_paths(tmp_path)):
        sug = {
            "suggestion_type": "approval_resolution_needed",
            "subject_type": "portfolio",
            "subject_key": "portfolio",
            "headline": "x",
            "reason": "r",
        }
        sug["suggestion_fingerprint"] = compute_suggestion_fingerprint(sug)
        ex = build_execution_from_suggestion(sug)
        eid = ex["execution_id"]
        with patch("app.services.collaboration_outcomes._capture_signal_bundle", return_value=_bundle()):
            mark_collaboration_execution_closed(eid, actor="t", reason="done")
        lo = list_collaboration_outcomes(window_days=30, limit=10)
        assert any((i.get("execution_id") == eid) for i in lo.get("items", []))
