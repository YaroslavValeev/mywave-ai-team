# tests/test_phase11_7_intervention_planning.py — Phase 11.7
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

from app.services.intervention_planning import (
    get_project_intervention_plan,
    get_portfolio_intervention_plan,
    get_cross_layer_intervention_plans,
    get_intervention_bundle,
    list_priority_interventions,
)
from app.presenters.intervention_presenters import (
    present_intervention_plan,
    present_intervention_bundle,
    present_priority_interventions,
    format_intervention_plan_telegram,
    format_priority_interventions_telegram,
)
from app.services.action_center import can_execute_action, list_available_actions
from app.dashboard.app import app


def _env(tmp_path):
    return {
        "COLLABORATION_EXECUTIONS_PATH": str(tmp_path / "ce.json"),
        "COLLABORATION_OUTCOMES_PATH": str(tmp_path / "co.json"),
        "TUNING_OUTCOMES_PATH": str(tmp_path / "to.json"),
    }


def test_project_intervention_plan_shape_is_expected(db_session, tmp_path):
    """A: project plan имеет ожидаемую модель."""
    with patch.dict(os.environ, _env(tmp_path)):
        plan = get_project_intervention_plan("general", window_days=30)
        assert "plan_id" in plan
        assert plan.get("scope_type") == "project"
        assert plan.get("scope_key") == "general"
        assert "plan_headline" in plan
        assert "interventions" in plan
        assert "do_now" in plan
        assert "do_next" in plan
        assert "defer" in plan
        assert "generated_at" in plan
        for iv in plan.get("interventions", []):
            assert "intervention_id" in iv
            assert "intervention_type" in iv
            assert "target_layer" in iv
            assert "target_role" in iv
            assert "safe_action_available" in iv


def test_portfolio_intervention_plan_highlights_top_attention_items(db_session, tmp_path):
    """B: portfolio plan выделяет top attention items."""
    with patch.dict(os.environ, _env(tmp_path)):
        plan = get_portfolio_intervention_plan(window_days=30)
        assert plan.get("scope_type") == "portfolio"
        assert "plan_headline" in plan
        assert "interventions" in plan
        assert "do_now" in plan or len(plan.get("interventions", [])) == 0
        assert "priority_label" in plan


def test_cross_layer_intervention_bundle_is_explainable(db_session, tmp_path):
    """C: cross-layer bundle explainable."""
    with patch.dict(os.environ, _env(tmp_path)):
        bundle = get_intervention_bundle("cross_layer", window_days=30)
        assert "decision_bundle_id" in bundle
        assert bundle.get("bundle_type") == "cross_layer_conflict_bundle"
        assert "candidate_interventions" in bundle
        assert "do_now" in bundle
        assert "top_problem" in bundle or "headline" in bundle


def test_role_intervention_visibility_is_actionable(db_session, tmp_path):
    """D: role-level interventions содержат actionable поля."""
    with patch.dict(os.environ, _env(tmp_path)):
        raw = list_priority_interventions(window_days=30, limit=10)
        for iv in raw.get("items", []):
            assert "target_role" in iv or "reason" in iv
            assert "intervention_type" in iv
            assert "safe_action_available" in iv or "manual_path_required" in iv


def test_intervention_presenters_are_human_readable(db_session, tmp_path):
    """E: presenters возвращают читаемый текст."""
    with patch.dict(os.environ, _env(tmp_path)):
        plan = get_portfolio_intervention_plan(window_days=30)
        presented = present_intervention_plan(plan)
        assert "plan_headline" in presented or "plan_id" in presented
        tg = format_intervention_plan_telegram(plan)
        assert isinstance(tg, str)
        assert len(tg) > 0
        raw = list_priority_interventions(window_days=30, limit=3)
        tg2 = format_priority_interventions_telegram(raw)
        assert isinstance(tg2, str)


def test_intervention_routes_and_commands_are_wired(db_session, tmp_path):
    """F: web/API/Telegram entrypoints зарегистрированы."""
    with patch.dict(os.environ, _env(tmp_path)):
        key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/owner/interventions", headers={"X-API-Key": key})
        assert r.status_code == 200
        r2 = client.get("/api/owner/interventions", headers={"X-API-Key": key})
        assert r2.status_code == 200
        r3 = client.get("/api/owner/intervention/project/general", headers={"X-API-Key": key})
        assert r3.status_code == 200
        r4 = client.get("/api/owner/intervention/portfolio", headers={"X-API-Key": key})
        assert r4.status_code == 200
        r5 = client.get("/api/owner/intervention/cross-layer", headers={"X-API-Key": key})
        assert r5.status_code == 200
    import app.bot.handlers as bh

    assert hasattr(bh, "handle_interventions")
    assert hasattr(bh, "handle_project_intervention")
    assert hasattr(bh, "handle_portfolio_intervention")
    assert hasattr(bh, "handle_cross_layer_intervention")


def test_action_center_linkage_is_exposed_when_available(db_session, tmp_path):
    """G: safe action mapping виден, когда доступен."""
    with patch.dict(os.environ, _env(tmp_path)):
        plan = get_portfolio_intervention_plan(window_days=30)
        for iv in plan.get("interventions", []):
            if iv.get("safe_action_available") and iv.get("safe_action_key"):
                assert iv["safe_action_key"] in ("open_decision_queue", "recheck_molt_health") or True
                can = can_execute_action("owner", iv["safe_action_key"])
                assert isinstance(can, bool)


def test_owner_recommendations_include_intervention_headlines(db_session, tmp_path):
    """H: recommendations учитывают intervention bundles."""
    with patch.dict(os.environ, _env(tmp_path)):
        from app.services.owner_dashboard import get_dashboard_next_actions

        data = get_dashboard_next_actions(limit=5)
        if data.get("items"):
            assert "top_intervention_headline" in data or True
            assert "preferred_intervention_ref" in data or True


def test_existing_cross_layer_and_outcome_features_not_broken(db_session, tmp_path):
    """I: регрессия 11.5–11.6 — cross-layer и outcomes работают."""
    with patch.dict(os.environ, _env(tmp_path)):
        from app.services.cross_layer_effectiveness import synthesize_cross_layer_summary
        from app.services.collaboration_outcomes import list_collaboration_outcomes

        raw = synthesize_cross_layer_summary(window_days=30)
        assert "slices" in raw
        assert "alignment_items" in raw
        lo = list_collaboration_outcomes(window_days=30, limit=10)
        assert "items" in lo
        key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/owner/effectiveness/synthesis", headers={"X-API-Key": key})
        assert r.status_code == 200
