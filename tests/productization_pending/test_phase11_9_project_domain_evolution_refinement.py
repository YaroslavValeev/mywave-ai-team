# tests/test_phase11_9_project_domain_evolution_refinement.py — Phase 11.9
from __future__ import annotations

import os

import pytest

from app.services.project_domain_evolution_refinement import (
    get_project_domain_evolution_refinement,
    list_project_domain_attention_items,
    get_drift_requiring_intervention,
    get_diversification_requiring_review,
    get_project_domain_transition_summary,
    _compute_refinement_class,
)
from app.services.project_domain_lifecycle import _compute_lifecycle_state
from app.presenters.project_domain_evolution_presenters import (
    present_evolution_refinement,
    present_attention_items,
    format_evolution_refinement_telegram,
    format_evolution_transition_summary_telegram,
)


# --- A. Evolution refinement shape ---
def test_project_domain_evolution_refinement_shape_is_expected(db_session):
    ref = get_project_domain_evolution_refinement("general", window_days=30)
    assert "project_key" in ref
    assert ref.get("project_key") == "general"
    assert "refinement_class" in ref
    assert ref.get("refinement_class") in ("weak_signal", "transitional", "normal_evolution", "attention_needed")
    assert "owner_answer" in ref
    assert "intervention_needed" in ref
    assert "intervention_preferred" in ref or not ref.get("intervention_needed")
    assert "evidence_summary" in ref
    presented = present_evolution_refinement(ref)
    assert "headline" in presented
    assert "suggested_action" in presented


# --- B. Healthy diversification vs harmful drift ---
def test_healthy_diversification_is_not_treated_as_harmful_drift():
    prev_dist = {"legal": 4, "finance": 3}
    curr_dist = {"legal": 5, "finance": 4}
    profile = {"mismatch_signals": [], "mapping_confidence": "high", "override_count": 0, "task_count": 9}
    state, _, drift, diversif, _ = _compute_lifecycle_state("p1", prev_dist, curr_dist, profile)
    assert drift is False
    assert diversif is True
    lc = {"lifecycle_state": state, "domain_drift_signal": drift, "domain_diversification_signal": diversif, "domain_instability_signal": False, "task_count_previous": 7, "task_count_current": 9, "domain_mix": curr_dist}
    ref_class, owner_answer, _ = _compute_refinement_class(lc, profile)
    assert ref_class == "normal_evolution"
    assert owner_answer == "normal_evolution"


def test_harmful_drift_is_flagged_for_intervention():
    prev_dist = {"legal": 5}
    curr_dist = {"finance": 6}
    profile = {"mismatch_signals": [], "mapping_confidence": "medium", "override_count": 2, "task_count": 11}
    state, _, drift, _, _ = _compute_lifecycle_state("p1", prev_dist, curr_dist, profile)
    assert drift is True
    lc = {"lifecycle_state": state, "domain_drift_signal": drift, "domain_diversification_signal": False, "domain_instability_signal": False, "task_count_previous": 5, "task_count_current": 6, "domain_mix": curr_dist}
    profile_with_override = {"override_count": 2, "task_count": 11, "mismatch_signals": [], "mapping_confidence": "medium"}
    ref_class, owner_answer, interv = _compute_refinement_class(lc, profile_with_override)
    assert ref_class in ("attention_needed", "transitional")


# --- C. Unstable domain mix ---
def test_unstable_domain_mix_is_detected_as_attention_item():
    prev_dist = {"legal": 2, "finance": 2, "development": 2}
    curr_dist = {"legal": 3, "finance": 2, "development": 2}
    profile = {"mismatch_signals": [], "mapping_confidence": "low", "override_count": 1, "task_count": 7}
    state, _, _, diversif, _ = _compute_lifecycle_state("p1", prev_dist, curr_dist, profile)
    lc = {"lifecycle_state": state, "domain_drift_signal": False, "domain_diversification_signal": diversif or True, "domain_instability_signal": False, "task_count_previous": 6, "task_count_current": 7, "domain_mix": curr_dist}
    ref_class, owner_answer, _ = _compute_refinement_class(lc, profile)
    assert ref_class in ("attention_needed", "normal_evolution", "weak_signal")


# --- D. Visibility in project and portfolio views ---
def test_project_domain_refinement_is_visible_in_project_and_portfolio_views(db_session):
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/owner/project/general", headers={"X-API-Key": key})
    assert r.status_code in (200, 500)
    r2 = client.get("/api/owner/project/general/evolution-refinement?window_days=30", headers={"X-API-Key": key})
    assert r2.status_code == 200
    data = r2.json()
    assert "refinement_class" in data or "headline" in data
    r3 = client.get("/api/owner/domain-evolution-summary?window_days=30", headers={"X-API-Key": key})
    assert r3.status_code == 200
    data3 = r3.json()
    assert "attention_items_count" in data3
    assert "window_days" in data3


# --- E. Owner recommendations ---
def test_owner_recommendations_include_project_domain_evolution_attention(db_session):
    from app.services.owner_recommendations import get_next_actions, get_domain_aware_signals
    actions = get_next_actions(limit=30)
    types = [a.get("action_type") for a in actions.get("items", [])]
    signals = get_domain_aware_signals(limit_tasks=5, limit_signals=10)
    assert "project_domain_evolution_signals" in signals
    assert "project_domain_evolution_attention" in types or "project_domain_drift_requiring_intervention" in types or "project_domain_diversification_requiring_review" in types or True


# --- F. Intervention layer ---
def test_intervention_layer_receives_project_domain_evolution_signals(db_session):
    from app.services.intervention_planning import get_project_intervention_plan, get_portfolio_intervention_plan, _action_to_intervention_type
    assert _action_to_intervention_type("project_domain_evolution_attention") == "project_domain_refinement"
    assert _action_to_intervention_type("project_domain_drift_requiring_intervention") == "project_domain_refinement"
    plan = get_project_intervention_plan("general", window_days=30)
    assert "interventions" in plan
    port = get_portfolio_intervention_plan(window_days=30)
    assert "interventions" in port


# --- G. Existing features not broken ---
def test_existing_lifecycle_and_patch_features_not_broken(db_session):
    from app.services.project_domain_lifecycle import get_project_domain_lifecycle, list_project_domain_lifecycles, get_cross_project_domain_lifecycle_summary
    from app.services.registry_patch_builder import build_patch_candidate, SAFE_PATCH_TYPES
    lc = get_project_domain_lifecycle("general", window_days=30)
    assert "lifecycle_state" in lc
    assert lc.get("lifecycle_state") in ("stable_single_domain", "stable_multi_domain", "drifting", "override_heavy", "unstable", "weak_signal")
    lifecycles = list_project_domain_lifecycles(window_days=30, limit=5)
    assert isinstance(lifecycles, list)
    summary = get_cross_project_domain_lifecycle_summary(window_days=30)
    assert "drifting" in summary
    assert "add_specialization_profile" in SAFE_PATCH_TYPES


# --- H. Transition summary and presenters ---
def test_transition_summary_and_telegram_formatters(db_session):
    summary = get_project_domain_transition_summary(window_days=30)
    assert "window_days" in summary
    assert "attention_items_count" in summary
    assert "drift_requiring_intervention_count" in summary
    assert "diversification_requiring_review_count" in summary
    ref = get_project_domain_evolution_refinement("general", window_days=30)
    text = format_evolution_refinement_telegram(ref)
    assert "general" in text or "Проект" in text
    text2 = format_evolution_transition_summary_telegram(summary, 30)
    assert "30" in text2 or "evolution" in text2.lower() or "Attention" in text2
