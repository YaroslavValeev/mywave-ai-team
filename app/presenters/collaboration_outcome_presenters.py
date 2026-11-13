# app/presenters/collaboration_outcome_presenters.py — Phase 11.5
from __future__ import annotations

from typing import Any, List


def present_collaboration_outcome_card(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {"has_outcome": False}
    return {
        "has_outcome": True,
        "outcome_id": raw.get("outcome_id"),
        "execution_id": raw.get("execution_id"),
        "outcome_status": raw.get("outcome_status"),
        "effectiveness_label": raw.get("effectiveness_label"),
        "outcome_reason": raw.get("outcome_reason"),
        "followup_needed": bool(raw.get("followup_needed")),
        "baseline_signal_state": raw.get("baseline_signal_state"),
        "post_execution_signal_state": raw.get("post_execution_signal_state"),
        "measured_at": raw.get("measured_at"),
        "window_days": raw.get("window_days"),
        "primary_metric": raw.get("primary_metric"),
        "subject_type": raw.get("subject_type"),
        "subject_key": raw.get("subject_key"),
    }


def present_collaboration_outcome_list(items: List[dict[str, Any]]) -> dict[str, Any]:
    cards = [present_collaboration_outcome_card(i) for i in (items or [])]
    return {"items": cards, "count": len(cards)}


def present_collaboration_effectiveness_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_days": raw.get("window_days"),
        "effective_executions_count": raw.get("effective_executions_count", 0),
        "ineffective_executions_count": raw.get("ineffective_executions_count", 0),
        "partially_effective_count": raw.get("partially_effective_count", 0),
        "not_enough_signal_count": raw.get("not_enough_signal_count", 0),
        "followup_needed_count": raw.get("followup_needed_count", 0),
        "total_outcomes_in_window": raw.get("total_outcomes_in_window", 0),
        "explainable": raw.get("explainable", True),
        "evidence_source": raw.get("evidence_source"),
        "effectiveness_by_execution_type": raw.get("effectiveness_by_execution_type") or {},
        "effectiveness_by_role_pair": raw.get("effectiveness_by_role_pair") or {},
        "effectiveness_by_project": raw.get("effectiveness_by_project") or {},
    }


def present_collaboration_effectiveness_hotspots(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_days": raw.get("window_days"),
        "items": raw.get("items") or [],
        "evidence_source": raw.get("evidence_source"),
    }


def present_followup_needed_items(raw: dict[str, Any]) -> dict[str, Any]:
    return present_collaboration_outcome_list(raw.get("items") or [])


def format_collaboration_outcome_card_telegram(raw: dict[str, Any]) -> str:
    c = present_collaboration_outcome_card(raw)
    if not c.get("has_outcome"):
        return "Нет сохранённого outcome для этого execution."
    lines = [
        f"Outcome {c.get('outcome_id')}",
        f"Execution: {c.get('execution_id')}",
        f"Статус: {c.get('outcome_status')} · эффективность: {c.get('effectiveness_label')}",
        f"Follow-up: {'да' if c.get('followup_needed') else 'нет'}",
        f"Почему: {c.get('outcome_reason') or '—'}",
    ]
    if c.get("baseline_signal_state"):
        lines.append(f"Baseline: {c['baseline_signal_state'][:200]}")
    if c.get("post_execution_signal_state"):
        lines.append(f"После: {c['post_execution_signal_state'][:200]}")
    return "\n".join(lines)


def format_collaboration_outcomes_list_telegram(items: List[dict[str, Any]], limit: int = 8) -> str:
    if not items:
        return "Нет outcomes в окне."
    lines = ["Collaboration outcomes (кратко):"]
    for i in items[:limit]:
        c = present_collaboration_outcome_card(i)
        lines.append(
            f"• {c.get('execution_id')}: {c.get('outcome_status')} / {c.get('effectiveness_label')} "
            f"{'[follow-up]' if c.get('followup_needed') else ''}"
        )
    return "\n".join(lines)


def format_collaboration_effectiveness_summary_telegram(raw: dict[str, Any]) -> str:
    s = present_collaboration_effectiveness_summary(raw)
    return (
        f"Эффективность collaboration ({s.get('window_days')}д):\n"
        f"effective={s.get('effective_executions_count')}, "
        f"ineffective={s.get('ineffective_executions_count')}, "
        f"partial={s.get('partially_effective_count')}, "
        f"no_signal={s.get('not_enough_signal_count')}, "
        f"follow-up={s.get('followup_needed_count')}\n"
        f"Источник: {s.get('evidence_source') or 'outcomes store'}"
    )


def format_followup_needed_telegram(raw: dict[str, Any]) -> str:
    items = raw.get("items") or []
    if not items:
        return "Follow-up по collaboration outcomes не требуется (или нет данных)."
    lines = [f"Нужен follow-up ({len(items)}):"]
    for i in items[:10]:
        c = present_collaboration_outcome_card(i)
        lines.append(f"• {c.get('execution_id')}: {c.get('outcome_reason', '')[:100]}")
    return "\n".join(lines)
