# app/presenters/domain_specialization_analytics_presenters.py — Phase 10.5: analytics view-models
from __future__ import annotations

from typing import Any, List


def present_domain_override_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для блока override summary (web)."""
    return {
        "total_overrides": raw.get("total_overrides", 0),
        "total_cleared": raw.get("total_cleared", 0),
        "unique_tasks_with_override": raw.get("unique_tasks_with_override", 0),
        "window_days": raw.get("window_days", 30),
        "override_rate": raw.get("override_rate", 0),
        "explainable": raw.get("explainable", True),
    }


def present_override_hotspots(raw: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """View-model для списка override hotspots."""
    return [
        {"type": h.get("type"), "key": h.get("key"), "count": h.get("count"), "reason_summary": (h.get("reason_summary") or "")[:120]}
        for h in raw
    ]


def present_specialization_fallback_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для блока fallback summary (web)."""
    return {
        "total_fallback_events": raw.get("total_fallback_events", 0),
        "total_selected_events": raw.get("total_selected_events", 0),
        "fallback_rate": raw.get("fallback_rate", 0),
        "unique_tasks_with_fallback": raw.get("unique_tasks_with_fallback", 0),
        "window_days": raw.get("window_days", 30),
        "explainable": raw.get("explainable", True),
    }


def present_specialization_hotspots(raw: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """View-model для списка specialization hotspots."""
    return [
        {
            "domain_key": h.get("domain_key"),
            "workflow_step": h.get("workflow_step"),
            "fallback_count": h.get("fallback_count"),
            "reason_summary": (h.get("reason_summary") or "")[:120],
        }
        for h in raw
    ]


def present_refinement_signals(raw: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """View-model для refinement signals."""
    return [
        {
            "signal_type": s.get("signal_type"),
            "severity": s.get("severity"),
            "reason": (s.get("reason") or "")[:200],
            "recommended_refinement_action": (s.get("recommended_refinement_action") or "")[:200],
            "evidence_summary": (s.get("evidence_summary") or "")[:150],
            "domain_key": s.get("domain_key"),
            "workflow_step": s.get("workflow_step"),
            "project_key": s.get("project_key"),
        }
        for s in raw
    ]


def present_refinement_backlog(raw: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """View-model для refinement backlog (web)."""
    return [
        {
            "refinement_item_key": b.get("refinement_item_key"),
            "item_type": b.get("item_type"),
            "domain_key": b.get("domain_key"),
            "workflow_step": b.get("workflow_step"),
            "project_key": b.get("project_key"),
            "severity": b.get("severity"),
            "reason": (b.get("reason") or "")[:200],
            "recommended_change": b.get("recommended_change"),
            "evidence_summary": (b.get("evidence_summary") or "")[:150],
            "window_days": b.get("window_days"),
        }
        for b in raw
    ]


# --- Telegram-friendly text formatters ---

def format_domain_override_summary_telegram(raw: dict[str, Any]) -> str:
    """Краткий текст для Telegram: override summary."""
    total = raw.get("total_overrides", 0)
    cleared = raw.get("total_cleared", 0)
    tasks = raw.get("unique_tasks_with_override", 0)
    days = raw.get("window_days", 30)
    rate = raw.get("override_rate", 0)
    return f"Domain override ({days} дн.): всего {total}, снято {cleared}, задач с override: {tasks}, rate: {rate}"


def format_override_hotspots_telegram(hotspots: List[dict[str, Any]], limit: int = 5) -> str:
    """Краткий текст для Telegram: override hotspots."""
    if not hotspots:
        return "Override hotspots: нет."
    lines = ["Override hotspots:"]
    for h in hotspots[:limit]:
        lines.append(f"  {h.get('type')} {h.get('key')}: {h.get('count')} — { (h.get('reason_summary') or '')[:60]}")
    return "\n".join(lines)


def format_specialization_fallback_summary_telegram(raw: dict[str, Any]) -> str:
    """Краткий текст для Telegram: fallback summary."""
    f = raw.get("total_fallback_events", 0)
    s = raw.get("total_selected_events", 0)
    rate = raw.get("fallback_rate", 0)
    tasks = raw.get("unique_tasks_with_fallback", 0)
    days = raw.get("window_days", 30)
    return f"Specialization fallback ({days} дн.): fallback {f}, selected {s}, rate {rate}, задач с fallback: {tasks}"


def format_specialization_hotspots_telegram(hotspots: List[dict[str, Any]], limit: int = 5) -> str:
    """Краткий текст для Telegram: spec hotspots."""
    if not hotspots:
        return "Specialization hotspots: нет."
    lines = ["Specialization hotspots:"]
    for h in hotspots[:limit]:
        lines.append(f"  {h.get('domain_key')} / {h.get('workflow_step')}: {h.get('fallback_count')}")
    return "\n".join(lines)


def format_refinement_backlog_telegram(backlog: List[dict[str, Any]], limit: int = 7) -> str:
    """Краткий текст для Telegram: refinement backlog."""
    if not backlog:
        return "Refinement backlog: пусто."
    lines = ["Refinement backlog:"]
    for b in backlog[:limit]:
        lines.append(f"  [{b.get('severity')}] {b.get('item_type')}: { (b.get('reason') or '')[:70]}")
        lines.append(f"    → {b.get('recommended_change', '')}")
    return "\n".join(lines)
