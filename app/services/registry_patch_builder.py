# app/services/registry_patch_builder.py — Phase 10.7: build patch candidate from refinement proposal
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, List, Optional

from app.services.refinement_exports import build_registry_patch_candidate
from app.services.refinement_proposal_store import get_proposal

_BASE = Path(__file__).resolve().parents[1]

SAFE_PATCH_TYPES = frozenset({
    "add_specialization_profile",
    "append_routing_keyword",
    "append_typical_request",
    "add_alias",
    "append_specialization_keyword",
    "append_guardrail_note",
    "update_summary_minor",
})


def _resolve_target_file(relative_path: Optional[str]) -> Optional[Path]:
    if not relative_path or " or " in (relative_path or ""):
        return None
    rp = (relative_path or "").strip()
    if rp.startswith("app/"):
        return _BASE / rp[4:]  # app/data/... -> data/... under app
    if rp.startswith("data/"):
        return _BASE / rp
    return _BASE / "data" / rp if rp else None


def _action_to_patch_type(candidate: dict[str, Any]) -> str:
    action = candidate.get("action") or ""
    if action == "add_entry":
        return "add_specialization_profile"
    if action == "append_routing_keyword":
        return "append_routing_keyword"
    if action == "add_alias":
        return "add_alias"
    if action == "append_specialization_keyword":
        return "append_specialization_keyword"
    if action == "append_guardrail_note":
        return "append_guardrail_note"
    if action == "update_summary_minor":
        return "update_summary_minor"
    if action == "adjust_keywords_or_add_alias":
        return "append_routing_keyword"
    return "manual_review"


def classify_patch_risk(proposal: dict[str, Any]) -> str:
    """Возвращает 'safe' или 'high_risk'."""
    candidate = build_registry_patch_candidate(proposal.get("proposal_id") or "")
    if candidate.get("error"):
        return "high_risk"
    ptype = _action_to_patch_type(candidate)
    if ptype in SAFE_PATCH_TYPES:
        return "safe"
    return "high_risk"


def get_patchable_changes(proposal: dict[str, Any]) -> List[dict[str, Any]]:
    """Список изменений, которые можно применить (для отчёта)."""
    candidate = build_registry_patch_candidate(proposal.get("proposal_id") or "")
    if candidate.get("error"):
        return []
    ptype = _action_to_patch_type(candidate)
    if ptype not in SAFE_PATCH_TYPES:
        return []
    target = _resolve_target_file(candidate.get("target_file"))
    if not target:
        return []
    return [{
        "patch_type": ptype,
        "target_file": str(target),
        "target_key": candidate.get("target_key"),
        "human_instruction": candidate.get("human_instruction", ""),
        "yaml_suggestion": candidate.get("yaml_suggestion"),
    }]


def build_patch_candidate(proposal_id: str) -> dict[str, Any]:
    """
    Построить patch candidate: target_file, patch_type, proposed mutation, diff_summary,
    safe/unsafe flag, validation prerequisites.
    """
    p = get_proposal(proposal_id)
    if not p:
        return {
            "error": "proposal not found",
            "proposal_id": proposal_id,
            "apply_allowed": False,
        }
    candidate = build_registry_patch_candidate(proposal_id)
    if candidate.get("error"):
        return {
            "error": candidate.get("error"),
            "proposal_id": proposal_id,
            "apply_allowed": False,
        }
    ptype = _action_to_patch_type(candidate)
    target_path = _resolve_target_file(candidate.get("target_file"))
    risk = "safe" if ptype in SAFE_PATCH_TYPES else "high_risk"
    apply_allowed = risk == "safe" and target_path is not None

    patch_id = f"patch_{proposal_id}_{int(time.time())}"

    return {
        "patch_id": patch_id,
        "proposal_id": proposal_id,
        "target_layer": "specializations" if "specializations" in (candidate.get("target_file") or "") else "domain_registry",
        "target_file": str(target_path) if target_path else candidate.get("target_file"),
        "target_path": target_path,
        "patch_type": ptype,
        "patch_scope": candidate.get("target_key") or "",
        "patch_status": "draft",
        "diff_summary": candidate.get("human_instruction", "")[:300],
        "validation_status": None,
        "backup_ref": None,
        "applied_at": None,
        "applied_by": None,
        "rollback_supported": apply_allowed,
        "apply_allowed": apply_allowed,
        "risk_level": risk,
        "raw_candidate": candidate,
        "proposal": p,
    }


def build_patch_preview(proposal_id: str) -> dict[str, Any]:
    """Preview: тот же shape что build_patch_candidate, с флагом preview."""
    out = build_patch_candidate(proposal_id)
    out["preview"] = True
    return out
