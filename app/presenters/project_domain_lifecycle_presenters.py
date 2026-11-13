# app/presenters/project_domain_lifecycle_presenters.py — Phase 10.8: lifecycle view-models
from __future__ import annotations

from typing import Any, List


def present_project_domain_lifecycle(raw: dict[str, Any]) -> dict[str, Any]:
    """Один lifecycle для web: compact, human-readable."""
    if not raw:
        return {}
    return {
        "project_key": raw.get("project_key"),
        "current_dominant_domain": raw.get("current_dominant_domain"),
        "previous_dominant_domain": raw.get("previous_dominant_domain"),
        "dominant_domain_stability": raw.get("dominant_domain_stability"),
        "domain_drift_signal": raw.get("domain_drift_signal"),
        "domain_diversification_signal": raw.get("domain_diversification_signal"),
        "domain_instability_signal": raw.get("domain_instability_signal"),
        "lifecycle_state": raw.get("lifecycle_state"),
        "reason": raw.get("reason"),
        "window_days": raw.get("window_days"),
        "task_count_previous": raw.get("task_count_previous"),
        "task_count_current": raw.get("task_count_current"),
        "domain_mix": raw.get("domain_mix"),
    }


def present_domain_drift_signals(items: List[dict[str, Any]]) -> dict[str, Any]:
    """Список drift-сигналов для web."""
    return {
        "items": [present_project_domain_lifecycle(x) for x in items],
        "count": len(items),
    }


def present_domain_diversification_signals(items: List[dict[str, Any]]) -> dict[str, Any]:
    """Список diversification-сигналов для web."""
    return {
        "items": [present_project_domain_lifecycle(x) for x in items],
        "count": len(items),
    }


def present_domain_instability_signals(items: List[dict[str, Any]]) -> dict[str, Any]:
    """Список instability-сигналов для web."""
    return {
        "items": [present_project_domain_lifecycle(x) for x in items],
        "count": len(items),
    }


def present_cross_project_domain_lifecycle_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Сводка cross-project lifecycle для web."""
    if not raw:
        return {}
    return {
        "window_days": raw.get("window_days"),
        "drifting_projects_count": raw.get("drifting_projects_count"),
        "diversification_projects_count": raw.get("diversification_projects_count"),
        "unstable_or_override_heavy_count": raw.get("unstable_or_override_heavy_count"),
        "by_lifecycle_state": raw.get("by_lifecycle_state"),
        "summary": raw.get("summary"),
        "drifting": [present_project_domain_lifecycle(x) for x in raw.get("drifting", [])],
        "diversification": [present_project_domain_lifecycle(x) for x in raw.get("diversification", [])],
        "unstable_or_override_heavy": [present_project_domain_lifecycle(x) for x in raw.get("unstable_or_override_heavy", [])],
    }


def format_project_lifecycle_telegram(lc: dict[str, Any]) -> str:
    """Один проект: lifecycle для Telegram."""
    if not lc:
        return "Нет данных по проекту."
    pk = lc.get("project_key", "?")
    state = lc.get("lifecycle_state", "?")
    curr = lc.get("current_dominant_domain") or "—"
    prev = lc.get("previous_dominant_domain") or "—"
    reason = (lc.get("reason") or "")[:120]
    lines = [f"Проект: {pk}", f"Домен (текущий): {curr}" + (f" · был: {prev}" if prev != "—" else ""), f"Состояние: {state}", reason]
    if lc.get("domain_drift_signal"):
        lines.append("⚠ Дрифт: доминанта сменилась")
    if lc.get("domain_instability_signal"):
        lines.append("⚠ Нестабильный профиль")
    return "\n".join(lines)


def format_domain_lifecycle_telegram(summary: dict[str, Any], window_days: int = 30) -> str:
    """Сводка domain lifecycle для Telegram: дрифтующие, override-heavy, нестабильные."""
    if not summary:
        return "Нет сводки за период."
    lines = [f"Domain lifecycle ({window_days} дн.):", summary.get("summary", "")]
    drift = summary.get("drifting", [])[:5]
    if drift:
        lines.append("Дрифт: " + ", ".join([x.get("project_key", "?") for x in drift]))
    unst = summary.get("unstable_or_override_heavy", [])[:5]
    if unst:
        lines.append("Нестабильные/override: " + ", ".join([x.get("project_key", "?") for x in unst]))
    return "\n".join(lines)
