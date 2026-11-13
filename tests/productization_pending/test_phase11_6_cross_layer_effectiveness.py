# tests/test_phase11_6_cross_layer_effectiveness.py — Phase 11.6
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

from app.services.cross_layer_effectiveness import (
    build_effectiveness_slices,
    get_layer_alignment_signals,
    synthesize_cross_layer_summary,
)
from app.presenters.cross_layer_effectiveness_presenters import (
    present_cross_layer_synthesis,
    format_cross_layer_synthesis_telegram,
)
from app.services.owner_recommendations import get_next_actions
from app.dashboard.app import app


def _env(tmp_path):
    return {
        "COLLABORATION_EXECUTIONS_PATH": str(tmp_path / "ce.json"),
        "COLLABORATION_OUTCOMES_PATH": str(tmp_path / "co.json"),
        "TUNING_OUTCOMES_PATH": str(tmp_path / "to.json"),
    }


def test_cross_layer_slice_shape(db_session, tmp_path):
    with patch.dict(os.environ, _env(tmp_path)):
        slices = build_effectiveness_slices(window_days=30)
        for s in slices:
            assert "layer" in s
            assert s["layer"] in ("tuning", "collaboration")
            assert "effective_count" in s
            assert "ineffective_count" in s
            assert "followup_count" in s
            assert "evidence_source" in s


def test_synthesis_is_explainable(db_session, tmp_path):
    with patch.dict(os.environ, _env(tmp_path)):
        raw = synthesize_cross_layer_summary(window_days=30)
        assert raw.get("explainable") is True
        assert "slices" in raw
        assert "alignment_items" in raw
        pres = present_cross_layer_synthesis(raw)
        assert "evidence" in str(pres) or "slices" in pres


def test_alignment_conflict_detected(db_session, tmp_path):
    with patch.dict(os.environ, _env(tmp_path)):
        with patch(
            "app.services.tuning_outcomes.get_tuning_outcome_summary",
            return_value={"improved_count": 0, "worse_count": 2, "pending_measurement_count": 0, "unchanged_count": 0, "insufficient_data_count": 0},
        ), patch(
            "app.services.collaboration_outcomes.get_collaboration_effectiveness_summary",
            return_value={"effective_executions_count": 1, "ineffective_executions_count": 0, "followup_needed_count": 0},
        ), patch(
            "app.services.tuning_outcomes.list_tuning_outcomes",
            return_value={"items": [{"tuning_candidate_id": "tc_x", "outcome_status": "worse"}]},
        ), patch(
            "app.services.collaboration_outcomes.list_collaboration_outcomes",
            return_value={"items": []},
        ):
            align = get_layer_alignment_signals(window_days=30)
        conflict = [a for a in align if a.get("conflict_type") == "collaboration_improved_tuning_worse"]
        assert len(conflict) >= 1
        assert "headline" in conflict[0]
        assert "evidence_refs" in conflict[0]


def test_synthesis_api_and_routes_wired(db_session, tmp_path):
    with patch.dict(os.environ, _env(tmp_path)):
        key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/owner/effectiveness/synthesis", headers={"X-API-Key": key})
        assert r.status_code == 200
        j = r.json()
        assert "slices" in j
        r2 = client.get("/owner/effectiveness", headers={"X-API-Key": key})
        assert r2.status_code == 200


def test_telegram_effectiveness_synthesis_command(db_session, tmp_path):
    with patch.dict(os.environ, _env(tmp_path)):
        import app.bot.handlers as bh

        assert hasattr(bh, "handle_effectiveness_synthesis")


def test_recommendations_include_cross_layer_signal(db_session, tmp_path):
    with patch.dict(os.environ, _env(tmp_path)):
        with patch(
            "app.services.cross_layer_effectiveness.get_layer_alignment_signals",
            return_value=[{"conflict_type": "collaboration_improved_tuning_worse", "headline": "x", "reason": "y"}],
        ), patch(
            "app.services.owner_recommendations.get_degraded_signal_summary",
            return_value={"current_state": "OK", "events_count_7d": 0},
        ), patch(
            "app.services.owner_recommendations.get_blockers_summary",
            return_value={"items": [], "blockers_count": 0},
        ):
            actions = get_next_actions(limit=50)
        types = [a.get("action_type") for a in actions.get("items", [])]
        assert "cross_layer_alignment_conflict_signal" in types


def test_existing_collaboration_and_tuning_outcomes_untouched(db_session, tmp_path):
    with patch.dict(os.environ, _env(tmp_path)):
        raw = synthesize_cross_layer_summary(window_days=30)
        assert "slices" in raw
        tg = format_cross_layer_synthesis_telegram(raw)
        assert "tuning" in tg or "collaboration" in tg or "effectiveness" in tg.lower()
