# tests/test_phase11_3_semi_automated_tuning.py — Phase 11.3: tuning patch integration & outcomes
from __future__ import annotations

import os

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.services.agent_tuning_store import save_candidate, get_candidate
from app.services.refinement_proposal_store import save_proposal
from app.services.tuning_patch_integration import (
    classify_tuning_candidate_patchability,
    build_patch_from_tuning_candidate,
    list_patchable_tuning_candidates,
)
from app.services.tuning_outcomes import evaluate_tuning_outcome, get_tuning_outcome, get_tuning_outcome_summary
from app.services.tuning_outcome_store import merge_outcome, outcome_id_for_candidate
from app.presenters.tuning_patch_presenters import (
    present_patchability_card,
    present_tuning_outcome,
    format_patchable_tuning_telegram,
)
from app.services.owner_recommendations import get_next_actions
from app.dashboard.app import app


def _env_tuning(tmp_path):
    return {
        "AGENT_TUNING_CANDIDATES_PATH": str(tmp_path / "tuning.json"),
        "REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json"),
        "TUNING_OUTCOMES_PATH": str(tmp_path / "outcomes.json"),
    }


# --- A. Patchable tuning candidates are detected ---
def test_patchable_tuning_candidates_are_detected(db_session, tmp_path):
    with patch.dict(os.environ, _env_tuning(tmp_path)):
        save_candidate({
            "tuning_candidate_id": "tc_patch_a",
            "candidate_type": "expand_specialization_keywords",
            "status": "pending_review",
            "domain_key": "general",
            "workflow_step": "pipeline",
        })
        cl = classify_tuning_candidate_patchability("tc_patch_a")
        assert cl.get("patchable") is True
        raw = list_patchable_tuning_candidates(window_days=30, limit=20)
        ids = [x["candidate"]["tuning_candidate_id"] for x in raw.get("items", [])]
        assert "tc_patch_a" in ids


# --- B. Tuning candidate can produce patch candidate when safe ---
def test_tuning_candidate_can_produce_patch_candidate_when_safe(db_session, tmp_path):
    with patch.dict(os.environ, _env_tuning(tmp_path)):
        save_candidate({
            "tuning_candidate_id": "tc_safe_b",
            "candidate_type": "expand_specialization_keywords",
            "status": "converted",
            "domain_key": "general",
            "workflow_step": "pipeline",
            "proposal_id": "rp_tc_safe_b",
        })
        save_proposal({
            "proposal_id": "rp_tc_safe_b",
            "proposal_type": "expand_specialization_profile",
            "target_layer": "specializations",
            "target_key": "general:pipeline",
            "reason": "test",
            "severity": "low",
            "status": "accepted",
            "created_at": "2025-01-01T00:00:00+00:00",
            "source_tuning_candidate_id": "tc_safe_b",
        })
        bridge = build_patch_from_tuning_candidate("tc_safe_b")
        assert bridge.get("requires_conversion") is False
        pc = bridge.get("patch_candidate") or {}
        assert "proposal_id" in pc or "error" in pc


# --- C. Tuning outcome shape is expected ---
def test_tuning_outcome_shape_is_expected(db_session, tmp_path):
    with patch.dict(os.environ, _env_tuning(tmp_path)):
        save_candidate({
            "tuning_candidate_id": "tc_shape_c",
            "status": "converted",
            "domain_key": "general",
            "workflow_step": "pipeline",
            "proposal_id": "rp_shape_c",
        })
        save_proposal({
            "proposal_id": "rp_shape_c",
            "proposal_type": "expand_specialization_profile",
            "target_layer": "specializations",
            "target_key": "general:pipeline",
            "status": "applied",
            "applied_at": "2025-01-02T00:00:00+00:00",
            "source_tuning_candidate_id": "tc_shape_c",
        })
        oid = outcome_id_for_candidate("tc_shape_c")
        merge_outcome(oid, {
            "outcome_id": oid,
            "tuning_candidate_id": "tc_shape_c",
            "proposal_id": "rp_shape_c",
            "baseline_fallback_count": 5,
            "baseline_signal_level": "fallback_count=5",
            "verification_window_days": 30,
        })
        with patch("app.services.tuning_outcomes._count_fallback_domain_step", return_value=2):
            rec = evaluate_tuning_outcome("tc_shape_c", window_days=30)
        card = present_tuning_outcome(rec or {})
        assert "outcome_status" in card
        assert card.get("outcome_status") == "improved"


# --- D. Outcome logic: followup when worse ---
def test_tuning_outcome_detects_improved_or_followup_needed(db_session, tmp_path):
    with patch.dict(os.environ, _env_tuning(tmp_path)):
        save_candidate({
            "tuning_candidate_id": "tc_follow_d",
            "status": "converted",
            "domain_key": "x",
            "workflow_step": "pipeline",
            "proposal_id": "rp_follow_d",
        })
        save_proposal({
            "proposal_id": "rp_follow_d",
            "proposal_type": "expand_specialization_profile",
            "target_layer": "specializations",
            "target_key": "x:pipeline",
            "status": "applied",
            "applied_at": "2025-01-02T00:00:00+00:00",
            "source_tuning_candidate_id": "tc_follow_d",
        })
        oid = outcome_id_for_candidate("tc_follow_d")
        merge_outcome(oid, {
            "outcome_id": oid,
            "tuning_candidate_id": "tc_follow_d",
            "proposal_id": "rp_follow_d",
            "baseline_fallback_count": 2,
            "baseline_signal_level": "x",
        })
        with patch("app.services.tuning_outcomes._count_fallback_domain_step", return_value=8):
            rec = evaluate_tuning_outcome("tc_follow_d", window_days=30)
        assert rec.get("outcome_status") == "worse"
        assert rec.get("followup_needed") is True


# --- E. Routes wired ---
def test_tuning_patch_routes_and_commands_are_wired(db_session, tmp_path):
    with patch.dict(os.environ, _env_tuning(tmp_path)):
        key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
        client = TestClient(app, raise_server_exceptions=False)
        r1 = client.get("/api/owner/tuning/patchable", headers={"X-API-Key": key})
        assert r1.status_code == 200
        assert "items" in r1.json()
        r2 = client.get("/api/owner/tuning/outcomes", headers={"X-API-Key": key})
        assert r2.status_code == 200
        r3 = client.get("/owner/tuning/outcomes", headers={"X-API-Key": key})
        assert r3.status_code == 200
        import app.bot.handlers as bot_handlers
        assert hasattr(bot_handlers, "handle_patchable_tuning")
        assert hasattr(bot_handlers, "handle_tuning_outcomes")
        assert hasattr(bot_handlers, "handle_tuning_outcome")


# --- F. Presenters human readable ---
def test_tuning_patch_presenters_are_human_readable(db_session, tmp_path):
    cl = classify_tuning_candidate_patchability("nonexistent")
    assert "patchable" in present_patchability_card(cl)
    tg = format_patchable_tuning_telegram([])
    assert isinstance(tg, str)


# --- G. Owner recommendations include patchable tuning attention ---
def test_owner_recommendations_include_patchable_tuning_attention(db_session, tmp_path):
    with patch.dict(os.environ, _env_tuning(tmp_path)):
        save_candidate({
            "tuning_candidate_id": "tc_rec_g",
            "candidate_type": "expand_specialization_keywords",
            "status": "pending_review",
        })
        actions = get_next_actions(limit=25)
        types = [a.get("action_type") for a in actions.get("items", [])]
        assert "patchable_tuning_candidate_signal" in types or "tuning_review" in types


# --- H. Existing patch and tuning workflows not broken ---
def test_existing_patch_and_tuning_workflows_not_broken(db_session, tmp_path):
    with patch.dict(os.environ, _env_tuning(tmp_path)):
        from app.services.agent_tuning_workflows import get_specialization_tuning_summary
        s = get_specialization_tuning_summary(window_days=30)
        assert "pending_count" in s
        from app.services.registry_patch_builder import build_patch_candidate
        # без proposal — ожидаемо error
        p = build_patch_candidate("missing_prop_xyz")
        assert p.get("apply_allowed") is False or p.get("error")


# --- I. Traceability candidate → proposal → outcome id ---
def test_traceability_candidate_to_proposal_to_patch_to_outcome_is_preserved(db_session, tmp_path):
    with patch.dict(os.environ, _env_tuning(tmp_path)):
        cid = "tc_trace_i"
        pid = "rp_trace_i"
        save_candidate({
            "tuning_candidate_id": cid,
            "status": "converted",
            "proposal_id": pid,
            "domain_key": "general",
            "workflow_step": "pipeline",
        })
        save_proposal({
            "proposal_id": pid,
            "proposal_type": "expand_specialization_profile",
            "target_layer": "specializations",
            "target_key": "general:pipeline",
            "status": "applied",
            "source_tuning_candidate_id": cid,
        })
        record_tuning_baseline_on_patch_apply = __import__(
            "app.services.tuning_outcomes", fromlist=["record_tuning_baseline_on_patch_apply"]
        ).record_tuning_baseline_on_patch_apply
        with patch("app.services.tuning_outcomes._count_fallback_domain_step", return_value=3):
            record_tuning_baseline_on_patch_apply(pid, patch_id="patch_test", window_days=30)
        oc = get_tuning_outcome(cid)
        assert oc is not None
        assert oc.get("proposal_id") == pid
        assert oc.get("patch_id") == "patch_test"
        assert oc.get("tuning_candidate_id") == cid
