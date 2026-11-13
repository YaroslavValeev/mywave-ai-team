# app/presenters/owner_portfolio_presenters.py — Phase 9.6: portfolio view-models
from __future__ import annotations

from typing import Any


def present_portfolio_overview(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для portfolio overview."""
    return {
        "projects_count": raw.get("projects_count", 0),
        "critical_count": raw.get("critical_count", 0),
        "attention_needed_count": raw.get("attention_needed_count", 0),
        "healthy_count": raw.get("healthy_count", 0),
        "total_active": raw.get("total_active", 0),
        "total_pending": raw.get("total_pending", 0),
        "rework_total": raw.get("rework_total", 0),
        "long_running_total": raw.get("long_running_total", 0),
        "system_state": raw.get("system_state", "OK"),
        "molt_ok": raw.get("molt_ok", True),
    }


def present_portfolio_health_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Compact health summary (same as overview for now)."""
    return present_portfolio_overview(raw)


def present_top_problem_projects(raw: dict[str, Any]) -> dict[str, Any]:
    """Top problem projects для web/text."""
    items = raw.get("items", [])
    return {
        "items": [
            {
                "project_key": p.get("project_key", ""),
                "project_label": p.get("project_label", p.get("project_key", "")),
                "status": p.get("status", ""),
                "reason": p.get("reason", ""),
                "pending_count": p.get("pending_count", 0),
                "rework_signals": p.get("rework_signals", 0),
                "long_running": p.get("long_running", 0),
                "active_count": p.get("active_count", 0),
            }
            for p in items
        ],
        "count": raw.get("count", len(items)),
    }


def present_approvals_backlog_by_project(raw: dict[str, Any]) -> dict[str, Any]:
    """Approvals backlog по проектам."""
    items = raw.get("items", [])
    return {
        "items": [
            {
                "project_key": p.get("project_key", ""),
                "project_label": p.get("project_label", p.get("project_key", "")),
                "pending_count": p.get("pending_count", 0),
            }
            for p in items
        ],
        "count": raw.get("count", len(items)),
    }


def present_rework_hotspots(raw: dict[str, Any]) -> dict[str, Any]:
    """Rework hotspots."""
    items = raw.get("items", [])
    return {"items": list(items), "count": raw.get("count", len(items))}


def present_degraded_hotspots(raw: dict[str, Any]) -> dict[str, Any]:
    """Degraded hotspots."""
    items = raw.get("items", [])
    return {
        "items": list(items),
        "count": raw.get("count", len(items)),
        "system_degraded": raw.get("system_degraded", False),
    }


def present_portfolio_focus_list(raw: dict[str, Any]) -> dict[str, Any]:
    """Focus list для owner."""
    items = raw.get("items", [])
    return {"items": list(items), "count": raw.get("count", len(items))}


def present_portfolio_digest(raw: dict[str, Any]) -> dict[str, Any]:
    """Portfolio digest view-model."""
    return {
        "window_days": raw.get("window_days", 7),
        "overview": present_portfolio_overview(raw.get("overview", {})),
        "top_problem_projects": raw.get("top_problem_projects", [])[:5],
        "focus_list": raw.get("focus_list", [])[:5],
        "approvals_backlog_count": raw.get("approvals_backlog_count", 0),
        "approvals_backlog_total": raw.get("approvals_backlog_total", 0),
        "rework_hotspots_count": raw.get("rework_hotspots_count", 0),
        "degraded_hotspots_count": raw.get("degraded_hotspots_count", 0),
        "system_degraded": raw.get("system_degraded", False),
    }


def format_portfolio_overview_text(data: dict[str, Any]) -> str:
    """Текст для Telegram /portfolio."""
    lines = [
        "📊 Портфель",
        f"Проектов: {data.get('projects_count', 0)} (critical: {data.get('critical_count', 0)}, attention: {data.get('attention_needed_count', 0)}, healthy: {data.get('healthy_count', 0)})",
        f"Active: {data.get('total_active', 0)} · Pending: {data.get('total_pending', 0)}",
        f"Rework сигналов: {data.get('rework_total', 0)} · Long-running: {data.get('long_running_total', 0)}",
        f"Система: {data.get('system_state', 'OK')}",
    ]
    lines.append("Подробнее: /owner/portfolio или /focus, /hotspots, /approvals_backlog")
    return "\n".join(lines)


def format_focus_list_text(data: dict[str, Any]) -> str:
    """Текст для Telegram /focus."""
    items = data.get("items", [])
    if not items:
        return "Focus list пуст — нет проектов, требующих срочного внимания.\n/portfolio — обзор портфеля."
    lines = ["🎯 Focus list (top projects for attention):"]
    for p in items:
        lines.append(f"• {p.get('project_label', p.get('project_key', '?'))} — {p.get('status', '?')}: {p.get('reason', '')[:60]}…")
        lines.append(f"  → {p.get('suggested_action', '')}")
    lines.append("\n/owner/portfolio — полный портфель")
    return "\n".join(lines)


def format_hotspots_text(rework: dict[str, Any], degraded: dict[str, Any]) -> str:
    """Текст для Telegram /hotspots (rework + degraded)."""
    lines = ["🔥 Hotspots"]
    r_items = rework.get("items", [])
    if r_items:
        lines.append("Rework:")
        for p in r_items[:5]:
            lines.append(f"  • {p.get('project_label', '?')}: {p.get('rework_signals', 0)} сигналов")
    else:
        lines.append("Rework: нет")
    if degraded.get("system_degraded"):
        d_items = degraded.get("items", [])
        lines.append("Degraded (затронутые проекты):")
        for p in d_items[:5]:
            lines.append(f"  • {p.get('project_label', '?')}: active {p.get('active_count', 0)}")
    else:
        lines.append("Degraded: система OK")
    lines.append("\n/owner/portfolio — портфель")
    return "\n".join(lines)


def format_portfolio_weekly_digest(payload: dict[str, Any]) -> str:
    """Текст portfolio weekly digest для уведомления."""
    lines = [f"📊 Portfolio digest ({payload.get('window_days', 7)} days)"]
    ov = payload.get("overview", {})
    if ov:
        lines.append(f"Проектов: {ov.get('projects_count', 0)} (critical: {ov.get('critical_count', 0)}, attention: {ov.get('attention_needed_count', 0)}, healthy: {ov.get('healthy_count', 0)})")
        lines.append(f"Total active: {ov.get('total_active', 0)} · pending: {ov.get('total_pending', 0)} · rework: {ov.get('rework_total', 0)}")
        lines.append(f"Система: {ov.get('system_state', 'OK')}")
    lines.append(f"Backlog проектов: {payload.get('approvals_backlog_count', 0)} · pending total: {payload.get('approvals_backlog_total', 0)}")
    lines.append(f"Rework hotspots: {payload.get('rework_hotspots_count', 0)} · Degraded hotspots: {payload.get('degraded_hotspots_count', 0)}")
    if payload.get("system_degraded"):
        lines.append("⚠️ Система degraded.")
    focus = payload.get("focus_list", [])[:3]
    if focus:
        labels = [str(p.get("project_label") or p.get("project_key") or "?") for p in focus]
        lines.append("Focus: " + ", ".join(labels))
    return "\n".join(lines)


def format_approvals_backlog_text(data: dict[str, Any]) -> str:
    """Текст для Telegram /approvals_backlog."""
    items = data.get("items", [])
    if not items:
        return "Approvals backlog по проектам пуст.\n/portfolio — обзор портфеля."
    lines = ["📋 Approvals backlog по проектам:"]
    for p in items[:10]:
        lines.append(f"  • {p.get('project_label', '?')}: {p.get('pending_count', 0)} pending")
    total = sum(p.get("pending_count", 0) for p in items)
    lines.append(f"Всего pending: {total}")
    lines.append("\n/owner/portfolio — портфель")
    return "\n".join(lines)
