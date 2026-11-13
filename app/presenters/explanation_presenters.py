# app/presenters/explanation_presenters.py — Phase 11.0: rationale view-models
from __future__ import annotations

from typing import Any, List


def present_rationale_card(raw: dict[str, Any]) -> dict[str, Any]:
    """Rationale card для web (short form)."""
    if not raw:
        return {}
    return {
        "headline": raw.get("headline", ""),
        "summary": raw.get("summary", ""),
        "evidence_items": raw.get("evidence_items", [])[:3],
        "recommended_action": raw.get("recommended_action"),
        "rationale_type": raw.get("rationale_type"),
        "confidence_label": raw.get("confidence_label", "medium"),
    }


def present_rationale_list(rationales: List[dict]) -> dict[str, Any]:
    """Список rationale cards."""
    cards = [present_rationale_card(r) for r in (rationales or [])]
    return {"items": cards, "count": len(cards)}


def present_task_explanation(raw: dict[str, Any]) -> dict[str, Any]:
    """Task explanation для web."""
    if not raw:
        return {}
    rationales = raw.get("rationales", [])
    return {
        "task_id": raw.get("task_id"),
        "project_key": raw.get("project_key"),
        "rationales": present_rationale_list(rationales).get("items", []),
        "count": len(rationales),
        "error": raw.get("error"),
        "headline": rationales[0].get("headline", "") if rationales else "Нет объяснений",
    }


def present_project_explanation(raw: dict[str, Any]) -> dict[str, Any]:
    """Project explanation для web."""
    if not raw:
        return {}
    rationales = raw.get("rationales", [])
    return {
        "project_key": raw.get("project_key"),
        "rationales": present_rationale_list(rationales).get("items", []),
        "count": len(rationales),
        "error": raw.get("error"),
        "headline": rationales[0].get("headline", "") if rationales else "Нет объяснений",
    }


def present_collaboration_explanation(raw: dict[str, Any]) -> dict[str, Any]:
    """Collaboration explanation для web."""
    if not raw:
        return {}
    rationales = raw.get("rationales", [])
    return {
        "project_key": raw.get("project_key"),
        "rationales": present_rationale_list(rationales).get("items", []),
        "count": len(rationales),
        "error": raw.get("error"),
    }


def present_refinement_explanation(raw: dict[str, Any]) -> dict[str, Any]:
    """Refinement explanation для web."""
    if not raw:
        return {}
    rationales = raw.get("rationales", [])
    return {
        "proposal_id": raw.get("proposal_id"),
        "rationales": present_rationale_list(rationales).get("items", []),
        "count": len(rationales),
        "error": raw.get("error"),
    }


def present_portfolio_explanation(raw: dict[str, Any]) -> dict[str, Any]:
    """Portfolio explanation для web."""
    if not raw:
        return {}
    rationales = raw.get("rationales", [])
    return {
        "rationales": present_rationale_list(rationales).get("items", []),
        "count": len(rationales),
        "window_days": raw.get("window_days"),
    }


def format_task_explanation_telegram(raw: dict[str, Any]) -> str:
    """Компактный текст task explanation для Telegram."""
    if raw.get("error"):
        return f"Ошибка: {raw['error']}"
    rationales = raw.get("rationales", [])[:3]
    if not rationales:
        return "Нет объяснений по задаче."
    lines = [f"Задача #{raw.get('task_id', '?')}:"]
    for r in rationales:
        lines.append(f"  • {r.get('headline', '')[:70]}")
        for e in (r.get("evidence_items") or [])[:2]:
            lines.append(f"    {e[:60]}")
    return "\n".join(lines)


def format_project_explanation_telegram(raw: dict[str, Any]) -> str:
    """Компактный текст project explanation для Telegram."""
    if raw.get("error"):
        return f"Ошибка: {raw['error']}"
    rationales = raw.get("rationales", [])[:3]
    if not rationales:
        return f"Нет объяснений по проекту {raw.get('project_key', '?')}."
    lines = [f"Проект {raw.get('project_key', '?')}:"]
    for r in rationales:
        lines.append(f"  • {r.get('headline', '')[:70]}")
    return "\n".join(lines)


def format_portfolio_explanation_telegram(raw: dict[str, Any]) -> str:
    """Компактный текст portfolio explanation для Telegram."""
    rationales = raw.get("rationales", [])[:5]
    if not rationales:
        return "Портфель: нет проектов в focus."
    lines = ["Портфель — почему в focus:"]
    for r in rationales:
        lines.append(f"  • {r.get('headline', '')[:70]}")
    return "\n".join(lines)


def format_collaboration_explanation_telegram(raw: dict[str, Any]) -> str:
    """Компактный текст collaboration explanation для Telegram."""
    if raw.get("error"):
        return f"Ошибка: {raw['error']}"
    rationales = raw.get("rationales", [])[:5]
    if not rationales:
        return "Collaboration: нет активных handoff."
    lines = ["Collaboration:"]
    for r in rationales:
        lines.append(f"  • {r.get('headline', '')[:70]}")
    return "\n".join(lines)


def format_refinement_explanation_telegram(raw: dict[str, Any]) -> str:
    """Компактный текст refinement explanation для Telegram."""
    if raw.get("error"):
        return f"Ошибка: {raw['error']}"
    rationales = raw.get("rationales", [])[:3]
    if not rationales:
        return "Refinement: нет proposals."
    lines = ["Refinement:"]
    for r in rationales:
        lines.append(f"  • {r.get('headline', '')[:70]}")
        if r.get("recommended_action"):
            lines.append(f"    → {r['recommended_action'][:50]}")
    return "\n".join(lines)
