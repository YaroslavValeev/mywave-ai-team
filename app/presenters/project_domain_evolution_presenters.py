# app/presenters/project_domain_evolution_presenters.py — Phase 11.9: evolution refinement view-models
from __future__ import annotations

from typing import Any, List


def present_evolution_refinement(raw: dict[str, Any]) -> dict[str, Any]:
    """Compact owner-friendly card для одного проекта."""
    if not raw:
        return {}
    return {
        "project_key": raw.get("project_key"),
        "refinement_class": raw.get("refinement_class"),
        "owner_answer": raw.get("owner_answer"),
        "intervention_needed": raw.get("intervention_needed"),
        "intervention_preferred": raw.get("intervention_preferred"),
        "linked_to_refinement_backlog": raw.get("linked_to_refinement_backlog"),
        "lifecycle_state": raw.get("lifecycle_state"),
        "headline": _owner_answer_headline(raw.get("owner_answer")),
        "suggested_action": _suggested_action(raw),
    }


def _owner_answer_headline(answer: str) -> str:
    m = {
        "normal_evolution": "Нормальная эволюция проекта",
        "review_recommended": "Рекомендуется review",
        "refinement_or_tuning": "Рассмотреть refinement/tuning",
        "owner_attention": "Требуется внимание owner",
    }
    return m.get(answer, answer or "—")


def _suggested_action(raw: dict[str, Any]) -> str:
    if not raw.get("intervention_needed"):
        return "—"
    pk = raw.get("project_key", "")
    pref = raw.get("intervention_preferred", "")
    if pref == "refinement_review":
        return f"/owner/project/{pk} · refinement backlog"
    if pref == "owner_attention":
        return f"/owner/project/{pk}"
    return f"/owner/project/{pk}"


def present_attention_items(items: List[dict[str, Any]]) -> dict[str, Any]:
    """Список attention items для web."""
    out = []
    for x in items:
        # Attention items have slightly different shape; ensure intervention_needed
        t = dict(x)
        t.setdefault("intervention_needed", True)
        out.append(present_evolution_refinement(t))
    return {"items": out, "count": len(items)}


def format_evolution_refinement_telegram(ref: dict[str, Any]) -> str:
    """Краткий формат для Telegram."""
    if not ref:
        return "Нет данных."
    pk = ref.get("project_key", "?")
    headline = _owner_answer_headline(ref.get("owner_answer"))
    state = ref.get("lifecycle_state", "—")
    lines = [f"Проект: {pk}", f"Вывод: {headline}", f"Состояние: {state}"]
    if ref.get("intervention_needed"):
        lines.append(f"→ {_suggested_action(ref)}")
    return "\n".join(lines)


def format_evolution_transition_summary_telegram(summary: dict[str, Any], window_days: int = 30) -> str:
    """Сводка transition summary для Telegram."""
    if not summary:
        return "Нет сводки."
    lines = [f"Domain evolution ({window_days} дн.):"]
    attn = summary.get("attention_items_count", 0)
    drift = summary.get("drift_requiring_intervention_count", 0)
    div = summary.get("diversification_requiring_review_count", 0)
    lines.append(f"Attention: {attn} · Drift (intervention): {drift} · Diversification (review): {div}")
    if attn > 0:
        for it in (summary.get("attention_items") or [])[:3]:
            pk = it.get("project_key", "?")
            headline = _owner_answer_headline(it.get("owner_answer"))
            lines.append(f"• {pk}: {headline}")
    return "\n".join(lines)
