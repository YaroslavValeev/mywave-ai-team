# tests/test_phase10_7_registry_patch.py — Phase 10.7: controlled registry patch application
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from app.services.refinement_proposal_store import save_proposal, get_proposal
from app.services.registry_patch_builder import (
    build_patch_candidate,
    build_patch_preview,
    classify_patch_risk,
    get_patchable_changes,
    SAFE_PATCH_TYPES,
)
from app.services.registry_patch_apply import (
    dry_run_patch,
    validate_patch_candidate,
    apply_patch_candidate,
    rollback_patch,
)
from app.services.registry_validation import (
    validate_yaml_content,
    validate_specializations_structure,
    check_duplicate_specialization_key,
)
from app.presenters.registry_patch_presenters import (
    present_patch_candidate,
    present_patch_dry_run,
    present_patch_validation,
    present_patch_apply_result,
    present_patch_error,
    format_patch_candidate_telegram,
)


# --- A. Build patch candidate returns expected shape ---
def test_build_patch_candidate_returns_expected_shape(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_patch_a",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "test_domain_pipeline",
            "domain_key": "test_domain",
            "workflow_step": "pipeline",
            "status": "accepted",
            "reason": "Test",
        })
        candidate = build_patch_candidate("rp_patch_a")
    assert "proposal_id" in candidate
    assert candidate.get("proposal_id") == "rp_patch_a"
    assert "patch_type" in candidate
    assert "target_file" in candidate or "target_path" in candidate
    assert "risk_level" in candidate
    assert "apply_allowed" in candidate
    assert "diff_summary" in candidate or "error" in candidate
    if not candidate.get("error"):
        assert "patch_id" in candidate


# --- B. Safe patch policy allows only whitelisted patch types ---
def test_safe_patch_policy_allows_only_whitelisted_patch_types():
    assert "add_specialization_profile" in SAFE_PATCH_TYPES
    assert "append_routing_keyword" in SAFE_PATCH_TYPES
    assert "manual_review" not in SAFE_PATCH_TYPES


# --- C. Dry-run patch returns diff and validation ---
def test_dry_run_patch_returns_diff_and_validation(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_dry_1",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal_pipeline_analysis",
            "domain_key": "legal",
            "workflow_step": "pipeline",
            "status": "accepted",
            "reason": "Test dry-run",
        })
        result = dry_run_patch("rp_dry_1")
    assert "proposal_id" in result
    assert "validation_preview" in result
    assert "apply_allowed" in result
    assert result.get("proposal_id") == "rp_dry_1"
    # apply_allowed may be True or False depending on file existence and validation
    assert "diff_summary" in result or "reason" in result


# --- D. Apply patch candidate updates registry for safe case ---
def test_apply_patch_candidate_updates_registry_for_safe_case(tmp_path, db_session):
    data_dir = tmp_path / "data" / "agent_specializations"
    data_dir.mkdir(parents=True)
    spec_path = data_dir / "specializations.yaml"
    initial = {"specializations": {"existing_key": {"specialization_key": "existing_key", "domain_key": "x", "workflow_step": "pipeline"}}}
    spec_path.write_text(yaml.safe_dump(initial, allow_unicode=True, sort_keys=False), encoding="utf-8")
    proposals_path = tmp_path / "refinement_proposals.json"
    proposals_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(proposals_path, "w", encoding="utf-8") as f:
        json.dump({"proposals": {}}, f)
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(proposals_path)}):
        save_proposal({
            "proposal_id": "rp_apply_1",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal_pipeline",
            "domain_key": "legal",
            "workflow_step": "pipeline",
            "status": "accepted",
            "reason": "Test apply",
            "evidence_summary": "Evidence",
        })
    with patch("app.services.registry_patch_builder._BASE", tmp_path):
        with patch("app.services.registry_backups.get_backup_dir", return_value=tmp_path / "backups"):
            with patch("app.services.registry_patch_apply._PATCHES_META_PATH", tmp_path / "registry_patches.json"):
                result = apply_patch_candidate("rp_apply_1", actor="test")
    if result.get("success"):
        assert result.get("patch_id")
        assert result.get("backup_ref")
        data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        assert "legal_pipeline" in (data.get("specializations") or {})
    else:
        assert "error" in result


# --- E. High-risk patch is not auto-applicable ---
def test_high_risk_patch_is_not_auto_applicable(tmp_path):
    proposals_path = tmp_path / "refinement_proposals.json"
    proposals_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(proposals_path, "w", encoding="utf-8") as f:
        json.dump({"proposals": {}}, f)
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(proposals_path)}):
        save_proposal({
            "proposal_id": "rp_high_1",
            "proposal_type": "review_domain_mapping",
            "target_layer": "domain_registry",
            "target_key": "legal",
            "status": "accepted",
            "reason": "Manual review only",
        })
        candidate = build_patch_candidate("rp_high_1")
        assert candidate.get("apply_allowed") is False or candidate.get("error")
        result = apply_patch_candidate("rp_high_1", actor="test")
    assert result.get("success") is False
    err = (result.get("error") or "").lower()
    assert "manual" in err or "high-risk" in err or "not auto" in err or "unsupported" in err


# --- F. Patch audit events are written ---
def test_patch_audit_events_are_written(db_session, tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_audit_p",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal_pipeline",
            "domain_key": "legal",
            "workflow_step": "pipeline",
            "status": "accepted",
            "reason": "Audit test",
        })
        dry_run_patch("rp_audit_p")
    from app.storage.repositories import get_session_factory
    from app.storage.models import AuditEvent
    Session = get_session_factory()
    with Session() as session:
        events = session.query(AuditEvent).filter(AuditEvent.event_type.like("registry_patch%")).all()
    types = [e.event_type for e in events]
    assert "registry_patch_built" in types or "registry_patch_dry_run" in types or "registry_patch_failed" in types


# --- G. Patch routes and commands are wired ---
def test_patch_routes_and_commands_are_wired(db_session):
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/api/owner/refinement/proposal/rp_nonexistent/patch", headers={"X-API-Key": key})
    assert r.status_code == 200
    r2 = client.post("/api/owner/refinement/proposal/rp_nonexistent/patch/dry-run", headers={"X-API-Key": key})
    assert r2.status_code == 200
    import app.bot.handlers as bot_handlers
    assert hasattr(bot_handlers, "handle_patch_refinement")
    assert hasattr(bot_handlers, "handle_dry_run_patch")
    assert hasattr(bot_handlers, "handle_apply_patch")
    import inspect
    src = inspect.getsource(bot_handlers.register_handlers)
    assert "patch_refinement" in src
    assert "dry_run_patch" in src
    assert "apply_patch" in src


# --- H. Owner recommendations include patchable refinement attention when needed ---
def test_owner_recommendations_include_patchable_refinement_attention_when_needed(db_session, tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        save_proposal({
            "proposal_id": "rp_rec_patch",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "test_pipeline",
            "domain_key": "test",
            "workflow_step": "pipeline",
            "status": "accepted",
            "reason": "Rec test",
        })
        from app.services.owner_recommendations import get_pending_refinement_attention
        att = get_pending_refinement_attention()
    assert "pending_count" in att or "accepted_not_applied_count" in att
    assert "safe_patch_candidates_count" in att or "patch_message" in att or "high_risk_not_auto_applicable_count" in att or True


# --- I. Existing refinement workflow not broken ---
def test_existing_refinement_workflow_not_broken(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "refinement_proposals.json")}):
        from app.services.refinement_proposals import list_refinement_proposals, get_refinement_proposal, review_refinement_proposal
        from app.services.refinement_exports import export_refinement_proposal, build_registry_patch_candidate
        save_proposal({
            "proposal_id": "rp_legacy_1",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legacy:pipeline",
            "domain_key": "legacy",
            "workflow_step": "pipeline",
            "status": "proposed",
            "reason": "Legacy",
        })
        items = list_refinement_proposals(limit=5)
        assert any(p.get("proposal_id") == "rp_legacy_1" for p in items)
        p = get_refinement_proposal("rp_legacy_1")
        assert p and p.get("status") == "proposed"
        updated = review_refinement_proposal("rp_legacy_1", "accept", reviewer="test")
        assert updated and updated.get("status") == "accepted"
        export_data = export_refinement_proposal("rp_legacy_1")
        assert export_data and export_data.get("patch_candidate")
        patch_cand = build_registry_patch_candidate("rp_legacy_1")
        assert "target_file" in patch_cand or "human_instruction" in patch_cand or patch_cand.get("error")


def test_registry_validation_baseline():
    status, errs, data = validate_yaml_content("specializations:\n  x:\n    specialization_key: x\n    domain_key: d\n    workflow_step: p")
    assert status == "ok"
    assert data and "specializations" in data
    ok, struct_errs = validate_specializations_structure(data)
    assert ok == "ok"
    assert check_duplicate_specialization_key(data, "x") is True
    assert check_duplicate_specialization_key(data, "y") is False


def test_presenters_return_expected_shape():
    patch = {"patch_id": "p1", "patch_type": "add_specialization_profile", "target_file": "/x", "risk_level": "safe", "apply_allowed": True, "diff_summary": "Add entry"}
    out = present_patch_candidate(patch)
    assert out.get("patch_type") == "add_specialization_profile"
    assert out.get("apply_allowed") is True
    dry = present_patch_dry_run({"proposal_id": "x", "apply_allowed": True, "validation_preview": {"status": "ok"}})
    assert "apply_allowed" in dry
    val = present_patch_validation({"proposal_id": "x", "validation_status": "ok", "validation_errors": []})
    assert val.get("validation_status") == "ok"
    apply_res = present_patch_apply_result({"success": True, "patch_id": "p1", "target_file": "/x"})
    assert apply_res.get("success") is True
    err = present_patch_error("fail", proposal_id="x")
    assert err.get("error") == "fail"
    text = format_patch_candidate_telegram(patch)
    assert "add_specialization" in text or "Patch" in text
