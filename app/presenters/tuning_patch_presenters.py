# app/presenters/tuning_patch_presenters.py — Phase 11.3: tuning patch & outcome view-models
from __future__ import annotations

from typing import Any, List


def present_patchable_tuning_candidate(item: dict[str, Any]) -> dict[str, Any]:
    """Элемент из list_patchable_tuning_candidates."""
    c = item.get("candidate") or {}
    p = item.get("patchability") or {}
    return {
        "tuning_candidate_id": c.get("tuning_candidate_id"),
        "status": c.get("status"),
        "problem_pattern": (c.get("problem_pattern") or "")[:120],
        "patchable": p.get("patchable"),
        "patchability_reason": p.get("patchability_reason"),
        "proposal_id": c.get("proposal_id") or p.get("proposal_id"),
        "patch_id": p.get("patch_id"),
        "change_type": p.get("change_type"),
        "expected_effect": p.get("expected_effect"),
    }


def present_tuning_patch_summary(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {}
    return {
        "patchable_count": raw.get("patchable_count", 0),
        "manual_or_blocked_count": raw.get("manual_or_blocked_count", 0),
        "applied_tuning_count": raw.get("applied_tuning_count", 0),
        "window_days": raw.get("window_days", 30),
        "explainable": raw.get("explainable", True),
    }


def present_tuning_outcome(rec: dict[str, Any]) -> dict[str, Any]:
    if not rec:
        return {}
    return {
        "outcome_id": rec.get("outcome_id"),
        "tuning_candidate_id": rec.get("tuning_candidate_id"),
        "proposal_id": rec.get("proposal_id"),
        "patch_id": rec.get("patch_id"),
        "verification_window_days": rec.get("verification_window_days"),
        "baseline_signal_level": rec.get("baseline_signal_level"),
        "post_apply_signal_level": rec.get("post_apply_signal_level"),
        "baseline_fallback_count": rec.get("baseline_fallback_count"),
        "post_apply_fallback_count": rec.get("post_apply_fallback_count"),
        "outcome_status": rec.get("outcome_status"),
        "outcome_reason": rec.get("outcome_reason"),
        "improvement_detected": rec.get("improvement_detected"),
        "followup_needed": rec.get("followup_needed"),
        "measured_at": rec.get("measured_at"),
    }


def present_tuning_outcome_summary(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {}
    return {
        "improved_count": raw.get("improved_count", 0),
        "worse_count": raw.get("worse_count", 0),
        "unchanged_count": raw.get("unchanged_count", 0),
        "pending_measurement_count": raw.get("pending_measurement_count", 0),
        "insufficient_data_count": raw.get("insufficient_data_count", 0),
        "not_patch_applied_count": raw.get("not_patch_applied_count", 0),
        "total_outcomes": raw.get("total_outcomes", 0),
        "window_days": raw.get("window_days", 30),
        "explainable": raw.get("explainable", True),
    }


def present_patchability_card(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {}
    return {
        "tuning_patch_id": raw.get("tuning_patch_id"),
        "tuning_candidate_id": raw.get("tuning_candidate_id"),
        "proposal_id": raw.get("proposal_id"),
        "patch_id": raw.get("patch_id"),
        "patchable": raw.get("patchable"),
        "patchability_reason": raw.get("patchability_reason"),
        "target_layer": raw.get("target_layer"),
        "target_file": raw.get("target_file"),
        "change_type": raw.get("change_type"),
        "status": raw.get("status"),
        "expected_effect": raw.get("expected_effect"),
        "verification_required": raw.get("verification_required"),
    }


def format_patchable_tuning_telegram(items: List[dict[str, Any]], limit: int = 8) -> str:
    if not items:
        return "Patchable tuning: нет записей."
    lines = ["Patchable tuning candidates:"]
    for it in items[:limit]:
        p = present_patchable_tuning_candidate(it)
        lines.append(f"  • {p.get('tuning_candidate_id')}: patchable={p.get('patchable')}")
        lines.append(f"    {str(p.get('patchability_reason', ''))[:70]}")
    return "\n".join(lines)


def format_tuning_outcomes_telegram(recs: List[dict[str, Any]], limit: int = 6) -> str:
    if not recs:
        return "Tuning outcomes: пусто."
    lines = ["Tuning outcomes:"]
    for r in recs[:limit]:
        p = present_tuning_outcome(r)
        lines.append(
            f"  • {p.get('tuning_candidate_id')}: {p.get('outcome_status')} — {str(p.get('outcome_reason', ''))[:55]}"
        )
    return "\n".join(lines)


def format_tuning_outcome_card_telegram(rec: dict[str, Any]) -> str:
    p = present_tuning_outcome(rec)
    if not p.get("tuning_candidate_id"):
        return "Outcome не найден."
    lines = [
        f"Outcome: {p.get('outcome_id')}",
        f"Candidate: {p.get('tuning_candidate_id')}",
        f"Status: {p.get('outcome_status')}",
        f"Причина: {p.get('outcome_reason', '')[:120]}",
    ]
    if p.get("baseline_signal_level"):
        lines.append(f"Baseline: {str(p.get('baseline_signal_level'))[:80]}")
    if p.get("post_apply_signal_level"):
        lines.append(f"Post: {str(p.get('post_apply_signal_level'))[:80]}")
    return "\n".join(lines)
