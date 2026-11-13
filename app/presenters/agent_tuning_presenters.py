# app/presenters/agent_tuning_presenters.py — Phase 11.2: tuning view-models
from __future__ import annotations

from typing import Any, List


def present_tuning_candidate_card(raw: dict[str, Any]) -> dict[str, Any]:
    """Tuning candidate card для web."""
    if not raw:
        return {}
    return {
        "tuning_candidate_id": raw.get("tuning_candidate_id", ""),
        "candidate_type": raw.get("candidate_type", ""),
        "specialization_key": raw.get("specialization_key", ""),
        "domain_key": raw.get("domain_key", ""),
        "workflow_step": raw.get("workflow_step", ""),
        "problem_pattern": raw.get("problem_pattern", ""),
        "recommended_tuning_change": raw.get("recommended_tuning_change", ""),
        "expected_effect": raw.get("expected_effect", ""),
        "severity": raw.get("severity", "low"),
        "status": raw.get("status", "pending_review"),
        "proposal_id": raw.get("proposal_id"),
        "verification_outcome": raw.get("verification_outcome"),
        "evidence_summary": raw.get("evidence_summary", [])[:3],
    }


def present_tuning_candidate_list(items: List[dict]) -> dict[str, Any]:
    """Список tuning candidate cards."""
    cards = [present_tuning_candidate_card(i) for i in (items or [])]
    return {"items": cards, "count": len(cards)}


def present_tuning_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Tuning summary для web."""
    if not raw:
        return {}
    return {
        "pending_count": raw.get("pending_count", 0),
        "accepted_count": raw.get("accepted_count", 0),
        "converted_count": raw.get("converted_count", 0),
        "verified_count": raw.get("verified_count", 0),
        "window_days": raw.get("window_days", 30),
    }


def present_tuning_verification(raw: dict[str, Any]) -> dict[str, Any]:
    """Verification результат."""
    if not raw:
        return {}
    return {
        "verification_outcome": raw.get("verification_outcome"),
        "verification_at": raw.get("verification_at"),
        "verification_notes": raw.get("verification_notes"),
    }


def format_tuning_candidates_telegram(raw: dict[str, Any]) -> str:
    """Компактный текст tuning candidates для Telegram."""
    items = raw.get("items", [])[:5]
    if not items:
        return "Нет tuning candidates."
    lines = ["Tuning candidates:"]
    for c in items:
        lines.append(f"  • {c.get('tuning_candidate_id', '')}: {c.get('problem_pattern', '')[:50]}")
        lines.append(f"    → {c.get('recommended_tuning_change', '')[:45]}")
    return "\n".join(lines)


def format_tuning_candidate_telegram(raw: dict[str, Any]) -> str:
    """Один candidate для Telegram."""
    if not raw:
        return "Candidate не найден."
    lines = [
        f"Tuning: {raw.get('tuning_candidate_id', '')}",
        f"Тип: {raw.get('candidate_type', '')}",
        f"Проблема: {raw.get('problem_pattern', '')[:80]}",
        f"Рекомендация: {raw.get('recommended_tuning_change', '')[:70]}",
        f"Status: {raw.get('status', '')}",
    ]
    if raw.get("proposal_id"):
        lines.append(f"Proposal: {raw['proposal_id']}")
    return "\n".join(lines)


def format_tuning_summary_telegram(raw: dict[str, Any]) -> str:
    """Tuning summary для Telegram."""
    if not raw:
        return "Нет данных."
    return (
        f"Tuning: pending={raw.get('pending_count', 0)}, "
        f"accepted={raw.get('accepted_count', 0)}, "
        f"converted={raw.get('converted_count', 0)}, "
        f"verified={raw.get('verified_count', 0)}"
    )
