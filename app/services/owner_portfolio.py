# app/services/owner_portfolio.py — Phase 9.6: portfolio (cross-project) layer
from __future__ import annotations

from typing import Any

from app.services.project_queries import list_projects
from app.services.owner_queries import get_system_status_summary


def get_portfolio_overview() -> dict[str, Any]:
    """Общая картина портфеля: проекты, health breakdown, system state."""
    projects_data = list_projects(limit=100)
    status = get_system_status_summary()
    items = projects_data.get("items", [])
    critical = sum(1 for p in items if p.get("status") == "critical")
    attention = sum(1 for p in items if p.get("status") == "attention_needed")
    healthy = sum(1 for p in items if p.get("status") == "healthy")
    total_active = sum(p.get("active_count", 0) for p in items)
    total_pending = sum(p.get("pending_count", 0) for p in items)
    rework_total = sum(p.get("rework_signals", 0) for p in items)
    long_running_total = sum(p.get("long_running", 0) for p in items)
    return {
        "projects_count": len(items),
        "critical_count": critical,
        "attention_needed_count": attention,
        "healthy_count": healthy,
        "total_active": total_active,
        "total_pending": total_pending,
        "rework_total": rework_total,
        "long_running_total": long_running_total,
        "system_state": status.get("state", "OK"),
        "molt_ok": status.get("molt_ok", True),
    }


def get_portfolio_health_summary() -> dict[str, Any]:
    """Краткая сводка здоровья портфеля (alias/compact для overview)."""
    return get_portfolio_overview()


def get_top_problem_projects(limit: int = 10) -> dict[str, Any]:
    """Ранжированный список проектов, требующих внимания (critical → attention_needed, по pending/rework/long_running)."""
    projects_data = list_projects(limit=100)
    items = projects_data.get("items", [])
    # Уже отсортировано в list_projects: critical, attention_needed, по -pending
    problem = [p for p in items if p.get("status") in ("critical", "attention_needed")]
    return {
        "items": problem[:limit],
        "count": len(problem[:limit]),
    }


def get_approvals_backlog_by_project(limit: int = 20) -> dict[str, Any]:
    """Где скапливаются pending approvals по проектам."""
    projects_data = list_projects(limit=100)
    items = [p for p in projects_data.get("items", []) if (p.get("pending_count") or 0) > 0]
    items.sort(key=lambda x: -(x.get("pending_count") or 0))
    return {"items": items[:limit], "count": len(items[:limit])}


def get_rework_hotspots(limit: int = 10) -> dict[str, Any]:
    """Проекты с повторным rework (rework_signals > 0)."""
    projects_data = list_projects(limit=100)
    items = [p for p in projects_data.get("items", []) if (p.get("rework_signals") or 0) > 0]
    items.sort(key=lambda x: -(x.get("rework_signals") or 0))
    out = []
    for p in items[:limit]:
        out.append({
            "project_key": p.get("project_key", ""),
            "project_label": p.get("project_label", p.get("project_key", "")),
            "rework_signals": p.get("rework_signals", 0),
            "reason": f"Повторный rework: {p.get('rework_signals', 0)} сигналов в проекте",
        })
    return {"items": out, "count": len(out)}


def get_degraded_hotspots(limit: int = 20) -> dict[str, Any]:
    """При DEGRADED — проекты с активной работой (затронуты)."""
    status = get_system_status_summary()
    if status.get("state") != "DEGRADED":
        return {"items": [], "count": 0, "system_degraded": False}
    projects_data = list_projects(limit=100)
    items = [p for p in projects_data.get("items", []) if (p.get("active_count") or 0) > 0]
    items.sort(key=lambda x: -(x.get("active_count") or 0))
    out = []
    for p in items[:limit]:
        out.append({
            "project_key": p.get("project_key", ""),
            "project_label": p.get("project_label", p.get("project_key", "")),
            "active_count": p.get("active_count", 0),
            "reason": "Система degraded; в проекте есть активные задачи — выполнение под риском",
        })
    return {"items": out, "count": len(out), "system_degraded": True}


def get_portfolio_focus_list(limit: int = 5) -> dict[str, Any]:
    """3–5 проектов для приоритетного внимания owner (actionable focus list)."""
    problem = get_top_problem_projects(limit=limit)
    items = problem.get("items", [])
    out = []
    for p in items:
        status = p.get("status", "")
        if status == "critical":
            suggested = "Срочно разобрать блокеры / approvals / rework по проекту"
        else:
            suggested = "Выделить время на проект: approvals или rework"
        out.append({
            "project_key": p.get("project_key", ""),
            "project_label": p.get("project_label", p.get("project_key", "")),
            "status": status,
            "reason": p.get("reason", ""),
            "pending_count": p.get("pending_count", 0),
            "rework_signals": p.get("rework_signals", 0),
            "long_running": p.get("long_running", 0),
            "suggested_action": suggested,
        })
    return {"items": out, "count": len(out)}


def get_portfolio_digest(window_days: int = 7) -> dict[str, Any]:
    """Portfolio-level сводка за окно (текущий snapshot как proxy)."""
    overview = get_portfolio_overview()
    top_problem = get_top_problem_projects(limit=5)
    focus = get_portfolio_focus_list(limit=5)
    backlog = get_approvals_backlog_by_project(limit=10)
    rework = get_rework_hotspots(limit=5)
    degraded = get_degraded_hotspots(limit=5)
    return {
        "window_days": window_days,
        "overview": overview,
        "top_problem_projects": top_problem.get("items", []),
        "focus_list": focus.get("items", []),
        "approvals_backlog_count": len(backlog.get("items", [])),
        "approvals_backlog_total": sum(p.get("pending_count", 0) for p in backlog.get("items", [])),
        "rework_hotspots_count": rework.get("count", 0),
        "degraded_hotspots_count": degraded.get("count", 0),
        "system_degraded": degraded.get("system_degraded", False),
    }
