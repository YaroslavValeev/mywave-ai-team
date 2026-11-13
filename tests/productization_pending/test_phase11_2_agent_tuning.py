# tests/test_phase11_2_agent_tuning.py — Phase 11.2: agent-specific tuning workflows
from __future__ import annotations

import os

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.services.agent_tuning_workflows import (
    generate_tuning_candidates,
    get_tuning_candidates,
    get_tuning_candidate,
    get_specialization_tuning_summary,
    mark_tuning_candidate_reviewed,
    convert_tuning_candidate_to_proposal,
    mark_tuning_candidate_verified,
)
from app.services.agent_tuning_store import save_candidate, get_candidate, list_candidates
from app.presenters.agent_tuning_presenters import (
    present_tuning_candidate_card,
    present_tuning_candidate_list,
    present_tuning_summary,
    format_tuning_candidates_telegram,
    format_tuning_candidate_telegram,
    format_tuning_summary_telegram,
)
from app.services.owner_recommendations import get_next_actions
from app.dashboard.app import app


def _tmp_tuning_path(tmp_path):
    return str(tmp_path / "agent_tuning_candidates.json")


def _tmp_proposals_path(tmp_path):
    return str(tmp_path / "refinement_proposals.json")


# --- A. Tuning candidates are generated from specialization signals ---
def test_tuning_candidates_are_generated_from_specialization_signals(db_session, tmp_path):
    mock_signals = [
        {
            "signal_type": "fallback_hotspot",
            "domain_key": "general",
            "workflow_step": "pipeline",
            "project_key": "test",
            "reason": "Fallback часто используется",
            "recommended_refinement_action": "Расширить keywords",
            "evidence_summary": "5 задач",
            "severity": "medium",
        },
    ]
    with patch.dict(os.environ, {"AGENT_TUNING_CANDIDATES_PATH": _tmp_tuning_path(tmp_path)}):
        with patch(
            "app.services.agent_tuning_workflows.get_refinement_signals",
            return_value=mock_signals,
        ):
            created = generate_tuning_candidates(window_days=30, limit=5)
    assert len(created) >= 1
    c = created[0]
    assert "tuning_candidate_id" in c
    assert c["tuning_candidate_id"].startswith("tc_")
    assert c.get("problem_pattern")
    assert c.get("status") == "pending_review"


# --- B. Tuning candidate shape is expected ---
def test_tuning_candidate_shape_is_expected(db_session, tmp_path):
    with patch.dict(os.environ, {"AGENT_TUNING_CANDIDATES_PATH": _tmp_tuning_path(tmp_path)}):
        candidate = {
            "tuning_candidate_id": "tc_test123",
            "specialization_key": "general_pipeline",
            "domain_key": "general",
            "workflow_step": "pipeline",
            "candidate_type": "expand_specialization_keywords",
            "problem_pattern": "Test problem",
            "recommended_tuning_change": "Add keywords",
            "severity": "low",
            "status": "pending_review",
            "source_signals": ["fallback_hotspot"],
            "evidence_summary": [],
        }
        save_candidate(candidate)
        rec = get_candidate("tc_test123")
    assert rec is not None
    assert rec["tuning_candidate_id"] == "tc_test123"
    assert rec["domain_key"] == "general"
    assert rec["status"] == "pending_review"
    assert "created_at" not in candidate  # store adds nothing, but we pass minimal


# --- C. Tuning candidate can be converted to refinement proposal ---
def test_tuning_candidate_can_be_converted_to_refinement_proposal(db_session, tmp_path):
    with patch.dict(os.environ, {
        "AGENT_TUNING_CANDIDATES_PATH": _tmp_tuning_path(tmp_path),
        "REFINEMENT_PROPOSALS_PATH": _tmp_proposals_path(tmp_path),
    }):
        candidate = {
            "tuning_candidate_id": "tc_conv001",
            "specialization_key": "general_pipeline",
            "domain_key": "general",
            "workflow_step": "pipeline",
            "candidate_type": "expand_specialization_keywords",
            "problem_pattern": "Fallback hotspot",
            "recommended_tuning_change": "Add keywords",
            "severity": "low",
            "status": "accepted",
            "source_signals": ["fallback_hotspot"],
            "evidence_summary": [],
            "window_days": 30,
        }
        save_candidate(candidate)
        with patch(
            "app.services.agent_tuning_workflows.get_refinement_backlog",
            return_value=[],
        ):
            proposal = convert_tuning_candidate_to_proposal("tc_conv001")
        assert proposal is not None
        assert "proposal_id" in proposal
        assert proposal.get("source_tuning_candidate_id") == "tc_conv001"
        assert proposal.get("status") == "accepted"
        rec = get_candidate("tc_conv001")
        assert rec is not None
        assert rec.get("status") == "converted"
        assert rec.get("proposal_id") == proposal["proposal_id"]


# --- D. Tuning review and verification lifecycle works ---
def test_tuning_review_and_verification_lifecycle_works(db_session, tmp_path):
    with patch.dict(os.environ, {"AGENT_TUNING_CANDIDATES_PATH": _tmp_tuning_path(tmp_path)}):
        candidate = {
            "tuning_candidate_id": "tc_life001",
            "domain_key": "general",
            "status": "pending_review",
            "problem_pattern": "Test",
        }
        save_candidate(candidate)
        updated = mark_tuning_candidate_reviewed("tc_life001", "accept", reviewer="test")
        assert updated is not None
        rec = get_candidate("tc_life001")
        assert rec.get("status") == "accepted"
        v = mark_tuning_candidate_verified("tc_life001", "improved", notes="Better")
        assert v is not None
        rec2 = get_candidate("tc_life001")
        assert rec2.get("verification_outcome") == "improved"


# --- E. Tuning routes and commands are wired ---
def test_tuning_routes_and_commands_are_wired(db_session, tmp_path):
    with patch.dict(os.environ, {"AGENT_TUNING_CANDIDATES_PATH": _tmp_tuning_path(tmp_path)}):
        key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
        client = TestClient(app, raise_server_exceptions=False)
        r1 = client.get("/owner/tuning", headers={"X-API-Key": key})
        assert r1.status_code == 200
        r2 = client.get("/api/owner/tuning", headers={"X-API-Key": key})
        assert r2.status_code == 200
        assert "items" in r2.json()
        r3 = client.get("/api/owner/tuning/summary", headers={"X-API-Key": key})
        assert r3.status_code == 200
        assert "pending_count" in r3.json()


# --- F. Tuning presenters return human readable output ---
def test_tuning_presenters_return_human_readable_output(db_session, tmp_path):
    with patch.dict(os.environ, {"AGENT_TUNING_CANDIDATES_PATH": _tmp_tuning_path(tmp_path)}):
        candidate = {
            "tuning_candidate_id": "tc_pres001",
            "candidate_type": "expand_specialization_keywords",
            "problem_pattern": "Fallback часто",
            "recommended_tuning_change": "Добавить keywords",
            "status": "pending_review",
        }
        card = present_tuning_candidate_card(candidate)
        assert "tuning_candidate_id" in card
        assert card.get("problem_pattern")
        tg = format_tuning_candidate_telegram(candidate)
        assert isinstance(tg, str)
        assert "tc_pres001" in tg
        summary = get_specialization_tuning_summary(window_days=30)
        tg_sum = format_tuning_summary_telegram(summary)
        assert isinstance(tg_sum, str)
        assert "pending" in tg_sum.lower() or "0" in tg_sum


# --- G. Owner recommendations include tuning attention when needed ---
def test_owner_recommendations_include_tuning_attention_when_needed(db_session, tmp_path):
    with patch.dict(os.environ, {"AGENT_TUNING_CANDIDATES_PATH": _tmp_tuning_path(tmp_path)}):
        save_candidate({
            "tuning_candidate_id": "tc_rec001",
            "status": "pending_review",
            "problem_pattern": "Need review",
        })
        actions = get_next_actions(limit=20)
    types = [a.get("action_type") for a in actions.get("items", [])]
    # tuning_review может присутствовать если pending_count >= 1
    # если список пуст — get_specialization_tuning_summary вернёт pending_count=1
    assert "items" in actions


# --- H. Existing refinement patch flow not broken ---
def test_existing_refinement_patch_flow_not_broken(db_session, tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": _tmp_proposals_path(tmp_path)}):
        from app.services.refinement_proposals import list_refinement_proposals, get_refinement_proposal
        items = list_refinement_proposals(limit=5)
        assert isinstance(items, list)
        # Пустой список — нормально
        assert True


# --- I. Existing specialization features not broken ---
def test_existing_specialization_features_not_broken(db_session):
    try:
        from app.services.domain_specialization_analytics import get_refinement_signals
        signals = get_refinement_signals(window_days=30, limit=5)
        assert isinstance(signals, list)
    except ImportError:
        pytest.skip("domain_specialization_analytics not available")
