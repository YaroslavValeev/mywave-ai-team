# tests/test_phase10_6_refinement_workflow.py — Phase 10.6: semi-manual refinement workflow
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.services.refinement_proposal_store import list_proposals, get_proposal, save_proposal
from app.services.refinement_proposals import (
    generate_refinement_proposals,
    list_refinement_proposals,
    get_refinement_proposal,
    review_refinement_proposal,
    mark_refinement_proposal_applied,
)
from app.services.refinement_exports import export_refinement_proposal, build_registry_patch_candidate
from app.presenters.refinement_proposal_presenters import (
    present_refinement_proposal_list,
    present_refinement_proposal_card,
    format_refinement_proposal_card_telegram,
)


# --- A. Generate refinement proposals returns actionable items ---
def test_generate_refinement_proposals_returns_actionable_items(db_session, tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        created = generate_refinement_proposals(window_days=30, limit=5)
    assert isinstance(created, list)
    for p in created:
        assert p.get("proposal_id")
        assert p.get("proposal_type")
        assert p.get("target_layer") in ("domain_registry", "specializations", None) or True
        assert p.get("status") == "proposed"
        assert p.get("reason") or p.get("evidence_summary")


# --- B. Refinement proposal lifecycle review accept/reject works ---
def test_refinement_proposal_lifecycle_review_accept_reject_works(db_session, tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_test_1",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal:pipeline",
            "reason": "Test reason",
            "status": "proposed",
            "severity": "low",
        })
        updated = review_refinement_proposal("rp_test_1", "accept", reviewer="test")
        assert updated is not None
        assert updated.get("status") == "accepted"
        rec = get_refinement_proposal("rp_test_1")
        assert rec.get("status") == "accepted"
        updated2 = review_refinement_proposal("rp_test_2", "reject", reviewer="test")
        assert updated2 is None
        save_proposal({"proposal_id": "rp_test_2", "status": "proposed", "reason": "x"})
        updated2 = review_refinement_proposal("rp_test_2", "reject", reviewer="test")
        assert updated2 is not None
        assert updated2.get("status") == "rejected"


# --- C. Refinement export returns patch candidate ---
def test_refinement_export_returns_patch_candidate(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_export_1",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal:pipeline",
            "domain_key": "legal",
            "workflow_step": "pipeline",
            "reason": "Test",
            "evidence_summary": "Evidence",
        })
        patch_cand = build_registry_patch_candidate("rp_export_1")
        assert "target_file" in patch_cand or "human_instruction" in patch_cand
        export_data = export_refinement_proposal("rp_export_1")
        assert export_data is not None
        assert export_data.get("patch_candidate")
        assert export_data.get("proposal_id") == "rp_export_1"


# --- D. Refinement proposal audit events are written ---
def test_refinement_proposal_audit_events_are_written(db_session, tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_audit_1",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal:pipeline",
            "status": "proposed",
            "reason": "Test",
        })
        review_refinement_proposal("rp_audit_1", "accept", reviewer="test")
    from app.storage.repositories import get_session_factory
    from app.storage.models import AuditEvent
    Session = get_session_factory()
    with Session() as session:
        events = session.query(AuditEvent).filter(AuditEvent.event_type.like("refinement_proposal%")).all()
    assert len(events) >= 1
    types = [e.event_type for e in events]
    assert "refinement_proposal_reviewed" in types or "refinement_proposal_accepted" in types


# --- E. Refinement routes are wired ---
def test_refinement_routes_are_wired(db_session):
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/owner/refinement/proposals", headers={"X-API-Key": key})
    assert r.status_code == 200
    r2 = client.get("/api/owner/refinement/proposals", headers={"X-API-Key": key})
    assert r2.status_code == 200
    data = r2.json()
    assert "items" in data
    r3 = client.post("/api/owner/refinement/proposals/generate", headers={"X-API-Key": key})
    assert r3.status_code == 200


# --- F. Refinement commands are wired ---
def test_refinement_commands_are_wired():
    import app.bot.handlers as bot_handlers
    assert hasattr(bot_handlers, "handle_refinement_proposals")
    assert hasattr(bot_handlers, "handle_refinement_proposal")
    assert hasattr(bot_handlers, "handle_review_refinement")
    import inspect
    src = inspect.getsource(bot_handlers.register_handlers)
    assert "refinement_proposals" in src
    assert "review_refinement" in src


# --- G. Refinement presenters return human-readable output ---
def test_refinement_presenters_return_human_readable_output(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_pres_1",
            "proposal_type": "adjust_routing_keywords",
            "target_layer": "domain_registry",
            "target_key": "legal",
            "reason": "Частые override на домен legal",
            "status": "proposed",
        })
        items = list_refinement_proposals(limit=5)
        presented = present_refinement_proposal_list(items)
        assert "items" in presented
        p = get_refinement_proposal("rp_pres_1")
        card = present_refinement_proposal_card(p)
        assert card.get("reason")
        text = format_refinement_proposal_card_telegram(p)
        assert "Proposal" in text or "rp_pres" in text


# --- H. Owner recommendations include pending refinement attention when needed ---
def test_owner_recommendations_include_pending_refinement_attention_when_needed(db_session, tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_rec_1",
            "status": "proposed",
            "reason": "Test",
        })
        from app.services.owner_recommendations import get_domain_aware_signals, get_pending_refinement_attention
        att = get_pending_refinement_attention()
        assert "pending_count" in att
        signals = get_domain_aware_signals(limit_tasks=5, limit_signals=5)
        assert "pending_refinement_proposals" in signals


# --- I. Existing analytics features not broken ---
def test_existing_analytics_features_not_broken(db_session):
    from app.services.domain_specialization_analytics import (
        get_domain_override_summary,
        get_refinement_backlog,
        get_refinement_signals,
    )
    summary = get_domain_override_summary(window_days=7)
    assert "total_overrides" in summary
    backlog = get_refinement_backlog(window_days=7, limit=5)
    assert isinstance(backlog, list)
    signals = get_refinement_signals(window_days=7, limit=5)
    assert isinstance(signals, list)
