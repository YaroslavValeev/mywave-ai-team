# app/services/tuning_patch_integration.py — Phase 11.3: bridge tuning ↔ refinement proposal ↔ patch candidate
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from app.services.agent_tuning_store import get_candidate, list_candidates
from app.services.refinement_proposal_store import get_proposal
from app.services.refinement_exports import build_registry_patch_candidate
from app.services.registry_patch_builder import build_patch_candidate


def _change_type_from_candidate(c: dict[str, Any]) -> str:
    ct = (c.get("candidate_type") or "").lower()
    if "expand" in ct or "keyword" in ct:
        return "add_specialization_profile"
    if "execution" in ct or "focus" in ct:
        return "expand_execution_focus_note"
    if "fallback" in ct or "review" in ct:
        return "manual_only"
    return "small_profile_adjustment"


def classify_tuning_candidate_patchability(candidate_id: str) -> dict[str, Any]:
    """
    Классификация patchability для tuning candidate (до или после conversion).
    Explainable flags; не выполняет apply.
    """
    c = get_candidate(candidate_id)
    if not c:
        return {"error": "candidate not found", "tuning_candidate_id": candidate_id, "patchable": False}

    ctype = (c.get("candidate_type") or "").lower()
    proposal_id = c.get("proposal_id")
    change_type = _change_type_from_candidate(c)

    # Heuristic: expand specialization path → safe after proposal
    if "expand" in ctype or "keyword" in ctype:
        preview_patchable = True
        reason = "После accept и to-proposal ожидается proposal expand_specialization_profile → safe add profile (если нет дубликата ключа)"
        manual = False
    elif "adjust_execution" in ctype or "focus" in ctype:
        preview_patchable = False
        reason = "Изменение execution focus / routing без safe file apply — только manual review"
        manual = True
        change_type = "manual_only"
    elif "review" in ctype or "strategy" in ctype:
        preview_patchable = False
        reason = "Стратегический review — human-only"
        manual = True
        change_type = "manual_only"
    else:
        preview_patchable = False
        reason = "Требуется ручная классификация или conversion в proposal"
        manual = True

    proposal_patch: Optional[dict[str, Any]] = None
    patchable = preview_patchable
    patchability_reason = reason
    target_layer = "specializations"
    target_file = None
    status = "preview"

    if proposal_id:
        p = get_proposal(proposal_id)
        patch = build_patch_candidate(proposal_id)
        proposal_patch = patch
        _ = build_registry_patch_candidate(proposal_id)
        apply_allowed = bool(patch.get("apply_allowed"))
        patchable = apply_allowed
        if apply_allowed:
            patchability_reason = "Proposal связан; patch candidate помечен как apply_allowed (Phase 10.7)"
            status = "patch_built"
        elif patch.get("error"):
            patchability_reason = f"Patch build: {patch.get('error')}"
            status = "blocked"
        else:
            patchability_reason = "Proposal есть, но auto-apply недоступен (high_risk или нет target_file)"
            status = "manual_only"
        target_file = patch.get("target_file")
        target_layer = patch.get("target_layer") or target_layer
        if isinstance(p, dict) and (p.get("status") == "applied"):
            status = "applied"

    tuning_patch_id = f"tp_{candidate_id}" + (f"_{proposal_id}" if proposal_id else "")

    return {
        "tuning_patch_id": tuning_patch_id,
        "tuning_candidate_id": candidate_id,
        "proposal_id": proposal_id,
        "patch_id": (proposal_patch or {}).get("patch_id"),
        "patchable": patchable,
        "patchability_reason": patchability_reason,
        "target_layer": target_layer,
        "target_file": target_file,
        "change_type": change_type,
        "expected_effect": c.get("expected_effect") or "Снижение fallback / стабильность execution lane",
        "verification_required": True,
        "status": status,
        "manual_only": manual and not proposal_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "applied_at": (get_proposal(proposal_id) or {}).get("applied_at") if proposal_id else None,
        "verified_at": c.get("verification_at"),
    }


def build_patch_from_tuning_candidate(candidate_id: str) -> dict[str, Any]:
    """
    Полная связка: candidate → proposal (если есть) → patch candidate.
    Без conversion; если нет proposal — возвращает classify + requires_conversion.
    """
    c = get_candidate(candidate_id)
    if not c:
        return {"error": "candidate not found", "tuning_candidate_id": candidate_id}

    cls = classify_tuning_candidate_patchability(candidate_id)
    if not c.get("proposal_id"):
        return {
            "requires_conversion": True,
            "classification": cls,
            "message": "Сначала accept и POST to-proposal",
        }

    pid = c["proposal_id"]
    patch = build_patch_candidate(pid)
    export = build_registry_patch_candidate(pid)
    return {
        "requires_conversion": False,
        "classification": cls,
        "patch_candidate": patch,
        "registry_patch_candidate": export,
        "tuning_candidate_id": candidate_id,
        "proposal_id": pid,
    }


def list_patchable_tuning_candidates(window_days: int = 30, limit: int = 30) -> dict[str, Any]:
    """Кандидаты, для которых classify.patchable True (preview или с proposal)."""
    items: List[dict[str, Any]] = []
    for c in list_candidates(limit=200):
        if c.get("status") == "rejected":
            continue
        cid = c.get("tuning_candidate_id")
        if not cid:
            continue
        cl = classify_tuning_candidate_patchability(cid)
        if cl.get("patchable"):
            items.append({"candidate": c, "patchability": cl})
    items = items[:limit]
    return {"items": items, "count": len(items), "window_days": window_days}


def list_manual_tuning_candidates(limit: int = 30) -> dict[str, Any]:
    """Кандидаты с manual_only / не patchable."""
    out: List[dict[str, Any]] = []
    for c in list_candidates(limit=200):
        if c.get("status") == "rejected":
            continue
        cid = c.get("tuning_candidate_id")
        if not cid:
            continue
        cl = classify_tuning_candidate_patchability(cid)
        if not cl.get("patchable") and not cl.get("error"):
            out.append({"candidate": c, "patchability": cl})
    return {"items": out[:limit], "count": min(len(out), limit)}


def get_tuning_patch_summary(window_days: int = 30) -> dict[str, Any]:
    """Сводка patchable / manual / applied tuning path."""
    patchable = list_patchable_tuning_candidates(window_days=window_days, limit=100)
    manual = list_manual_tuning_candidates(limit=100)
    applied = 0
    for c in list_candidates(limit=200):
        cl = classify_tuning_candidate_patchability(c.get("tuning_candidate_id", ""))
        if cl.get("status") == "applied":
            applied += 1
    return {
        "patchable_count": patchable.get("count", 0),
        "manual_or_blocked_count": manual.get("count", 0),
        "applied_tuning_count": applied,
        "window_days": window_days,
        "explainable": True,
    }


def get_tuning_patch_candidate(candidate_id: str) -> dict[str, Any]:
    """Alias: classify + optional patch payload."""
    return classify_tuning_candidate_patchability(candidate_id)
