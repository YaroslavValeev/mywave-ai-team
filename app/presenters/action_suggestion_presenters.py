# app/presenters/action_suggestion_presenters.py — Phase 11.1: action suggestion view-models
from __future__ import annotations

from typing import Any, List


def present_action_suggestion_card(raw: dict[str, Any]) -> dict[str, Any]:
    """Suggestion card для web (short form)."""
    if not raw:
        return {}
    return {
        "suggestion_id": raw.get("suggestion_id", ""),
        "suggestion_type": raw.get("suggestion_type", ""),
        "headline": raw.get("headline", ""),
        "reason": raw.get("reason", ""),
        "evidence_summary": raw.get("evidence_summary", [])[:3],
        "recommended_next_step": raw.get("recommended_next_step", ""),
        "urgency": raw.get("urgency", "medium"),
        "safe_action_available": raw.get("safe_action_available"),
        "target_role": raw.get("target_role", ""),
        "suggestion_fingerprint": raw.get("suggestion_fingerprint"),
        "execution_exists": raw.get("execution_exists"),
        "execution_id": raw.get("execution_id"),
        "executable": raw.get("executable"),
        "pending_executions_for_subject": raw.get("pending_executions_for_subject"),
    }


def present_action_suggestion_list(suggestions: List[dict]) -> dict[str, Any]:
    """Список suggestion cards."""
    cards = [present_action_suggestion_card(s) for s in (suggestions or [])]
    return {"items": cards, "count": len(cards)}


def present_decision_support_card(raw: dict[str, Any]) -> dict[str, Any]:
    """Decision support card для web."""
    if not raw:
        return {}
    return {
        "decision_support_id": raw.get("decision_support_id", ""),
        "headline": raw.get("headline", ""),
        "why_now": raw.get("why_now", ""),
        "options": raw.get("options", [])[:3],
        "preferred_option": raw.get("preferred_option", ""),
        "preferred_option_reason": raw.get("preferred_option_reason", ""),
        "risk_if_ignored": raw.get("risk_if_ignored", ""),
        "evidence_items": raw.get("evidence_items", [])[:3],
    }


def present_decision_support_list(items: List[dict]) -> dict[str, Any]:
    """Список decision support cards."""
    cards = [present_decision_support_card(i) for i in (items or [])]
    return {"items": cards, "count": len(cards)}


def format_suggestions_telegram(raw: dict[str, Any]) -> str:
    """Компактный текст suggestions для Telegram."""
    suggestions = raw.get("suggestions", [])[:5]
    if not suggestions:
        return "Нет suggestions за период."
    lines = ["Action suggestions:"]
    for s in suggestions:
        lines.append(f"  • {s.get('headline', '')[:60]}")
        lines.append(f"    → {s.get('recommended_next_step', '')[:50]}")
        if s.get("safe_action_available"):
            lines.append(f"    /do {s['safe_action_available']}")
    return "\n".join(lines)


def format_decision_support_telegram(raw: dict[str, Any]) -> str:
    """Компактный текст decision support для Telegram."""
    items = raw.get("items", [])[:3]
    if not items:
        return "Нет decision support."
    lines = ["Decision support:"]
    for i in items:
        lines.append(f"  • {i.get('headline', '')[:55]}")
        lines.append(f"    Рекомендация: {i.get('preferred_option', '')} — {i.get('preferred_option_reason', '')[:40]}")
        lines.append(f"    Риск: {i.get('risk_if_ignored', '')[:40]}")
    return "\n".join(lines)


def format_project_suggestions_telegram(raw: dict[str, Any]) -> str:
    """Project suggestions для Telegram."""
    suggestions = raw.get("suggestions", [])[:3]
    if not suggestions:
        return f"Проект {raw.get('project_key', '?')}: нет suggestions."
    lines = [f"Проект {raw.get('project_key', '?')}:"]
    for s in suggestions:
        lines.append(f"  • {s.get('headline', '')[:55]}")
        lines.append(f"    → {s.get('recommended_next_step', '')[:45]}")
    return "\n".join(lines)


def format_role_suggestions_telegram(raw: dict[str, Any]) -> str:
    """Role suggestions для Telegram."""
    suggestions = raw.get("suggestions", [])[:3]
    if not suggestions:
        return f"Роль {raw.get('role_key', '?')}: нет suggestions."
    lines = [f"Роль {raw.get('role_key', '?')}:"]
    for s in suggestions:
        lines.append(f"  • {s.get('headline', '')[:55]}")
        lines.append(f"    → {s.get('recommended_next_step', '')[:45]}")
    return "\n".join(lines)
