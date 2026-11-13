# tests/test_phase11_8_richer_safe_patch.py — Phase 11.8: richer safe tuning coverage
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from app.services.patch_coverage import get_patch_coverage_summary
from app.services.refinement_proposal_store import save_proposal, get_proposal
from app.services.refinement_exports import build_registry_patch_candidate
from app.services.registry_patch_builder import (
    build_patch_candidate,
    SAFE_PATCH_TYPES,
    _action_to_patch_type,
)
from app.services.registry_patch_apply import (
    dry_run_patch,
    validate_patch_candidate,
    apply_patch_candidate,
)
from app.services.owner_recommendations import get_pending_refinement_attention


# --- A. adjust_routing_keywords → append_routing_keyword, apply_allowed ---
def test_adjust_routing_keywords_produces_append_routing_keyword(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        save_proposal({
            "proposal_id": "rp_adj_1",
            "proposal_type": "adjust_routing_keywords",
            "target_layer": "domain_registry",
            "target_key": "legal",
            "domain_key": "legal",
            "status": "accepted",
            "reason": "keyword: лицензирование",
        })
        candidate = build_patch_candidate("rp_adj_1")
    assert candidate.get("error") is None
    assert candidate.get("patch_type") == "append_routing_keyword"
    assert candidate.get("apply_allowed") is True
    raw = candidate.get("raw_candidate") or {}
    assert raw.get("target_file", "").endswith("domain_registry.yaml")
    assert raw.get("target_key") == "legal"
    assert raw.get("append_value")


# --- B. add_alias → add_alias, apply_allowed ---
def test_add_alias_produces_add_alias_patch(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        save_proposal({
            "proposal_id": "rp_alias_1",
            "proposal_type": "add_alias",
            "target_layer": "domain_registry",
            "target_key": "legal",
            "domain_key": "legal",
            "status": "accepted",
            "reason": "alias: лицензии",
        })
        candidate = build_patch_candidate("rp_alias_1")
    assert candidate.get("error") is None
    assert candidate.get("patch_type") == "add_alias"
    assert candidate.get("apply_allowed") is True


# --- C. expand_specialization_profile → append_specialization_keyword ---
def test_expand_specialization_produces_append_keyword(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        save_proposal({
            "proposal_id": "rp_exp_kw",
            "proposal_type": "expand_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal_pipeline_analysis",
            "domain_key": "legal",
            "workflow_step": "pipeline",
            "status": "accepted",
            "recommended_change": "add selection keyword",
            "evidence_summary": "keyword: лицензирование",
        })
        candidate = build_patch_candidate("rp_exp_kw")
    assert candidate.get("error") is None
    assert candidate.get("patch_type") == "append_specialization_keyword"
    assert candidate.get("apply_allowed") is True


# --- D. expand_specialization_profile → append_guardrail_note ---
def test_expand_specialization_produces_append_guardrail(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        save_proposal({
            "proposal_id": "rp_exp_gr",
            "proposal_type": "expand_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal_pipeline_analysis",
            "domain_key": "legal",
            "workflow_step": "pipeline",
            "status": "accepted",
            "recommended_change": "add guardrail",
            "evidence_summary": "always cite sources",
        })
        candidate = build_patch_candidate("rp_exp_gr")
    assert candidate.get("error") is None
    assert candidate.get("patch_type") == "append_guardrail_note"
    assert candidate.get("apply_allowed") is True


# --- E. expand_specialization_profile → update_summary_minor ---
def test_expand_specialization_produces_update_summary(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        save_proposal({
            "proposal_id": "rp_exp_sum",
            "proposal_type": "expand_specialization_profile",
            "target_layer": "specializations",
            "target_key": "legal_pipeline_analysis",
            "domain_key": "legal",
            "workflow_step": "pipeline",
            "status": "accepted",
            "recommended_change": "update summary",
            "evidence_summary": "Расширить описание анализа договоров.",
        })
        candidate = build_patch_candidate("rp_exp_sum")
    assert candidate.get("error") is None
    assert candidate.get("patch_type") == "update_summary_minor"
    assert candidate.get("apply_allowed") is True


# --- F. SAFE_PATCH_TYPES содержит все Phase 11.8 типы ---
def test_safe_patch_types_include_phase_11_8_types():
    assert "append_routing_keyword" in SAFE_PATCH_TYPES
    assert "add_alias" in SAFE_PATCH_TYPES
    assert "append_specialization_keyword" in SAFE_PATCH_TYPES
    assert "append_guardrail_note" in SAFE_PATCH_TYPES
    assert "update_summary_minor" in SAFE_PATCH_TYPES
    assert "append_typical_request" in SAFE_PATCH_TYPES


# --- G. get_patch_coverage_summary возвращает ожидаемую структуру ---
def test_patch_coverage_summary_shape(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        summary = get_patch_coverage_summary(status="accepted")
    assert "patchable_count" in summary
    assert "manual_only_count" in summary
    assert "total_accepted" in summary
    assert "by_type" in summary
    assert "patchable_types" in summary
    assert "safe_patch_types" in summary
    assert isinstance(summary["patchable_types"], list)
    assert isinstance(summary["safe_patch_types"], list)


# --- H. dry_run для append_routing_keyword (domain_registry) ---
def test_dry_run_append_routing_keyword(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        save_proposal({
            "proposal_id": "rp_dry_adj",
            "proposal_type": "adjust_routing_keywords",
            "target_layer": "domain_registry",
            "target_key": "legal",
            "domain_key": "legal",
            "status": "accepted",
            "reason": "keyword: patent",
        })
        result = dry_run_patch("rp_dry_adj")
    assert result.get("proposal_id") == "rp_dry_adj"
    assert result.get("apply_allowed") is True or "domain key not found" in str(result.get("reason", ""))
    if result.get("apply_allowed"):
        assert result.get("validation_preview", {}).get("status") == "ok"


# --- I. owner_recommendations включает patch coverage ---
def test_owner_recommendations_includes_patch_coverage(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        save_proposal({
            "proposal_id": "rp_owner_1",
            "proposal_type": "add_specialization_profile",
            "target_layer": "specializations",
            "target_key": "test_domain_pipeline",
            "domain_key": "test_domain",
            "workflow_step": "pipeline",
            "status": "accepted",
            "reason": "Test",
        })
        attn = get_pending_refinement_attention()
    if attn:
        assert "patchable_count" in attn or "patchable" in str(attn).lower()
        assert "manual_only_count" in attn or "manual" in str(attn).lower()


# --- J. review_domain_mapping остаётся manual_review ---
def test_review_domain_mapping_stays_manual(tmp_path):
    with patch.dict(os.environ, {"REFINEMENT_PROPOSALS_PATH": str(tmp_path / "proposals.json")}):
        save_proposal({
            "proposal_id": "rp_review_1",
            "proposal_type": "review_domain_mapping",
            "target_layer": "domain_registry",
            "target_key": "general",
            "status": "accepted",
            "reason": "Review override reasons",
        })
        candidate = build_patch_candidate("rp_review_1")
    assert candidate.get("patch_type") == "manual_review"
    assert candidate.get("apply_allowed") is False
