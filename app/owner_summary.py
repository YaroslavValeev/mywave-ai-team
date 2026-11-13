# app/owner_summary.py — Phase 9.0: сбор краткой и детальной сводки для owner
from __future__ import annotations

from typing import Any

from app.services.owner_queries import (
    get_system_status_summary,
    get_active_tasks,
    get_pending_approvals,
    get_recent_artifacts,
    get_runs_summary,
)


def build_short_summary() -> dict[str, Any]:
    """Краткая сводка для /status: счётчики, molt, state."""
    return get_system_status_summary()


def build_detailed_summary(
    tasks_limit: int = 5,
    approvals_limit: int = 5,
    artifacts_limit: int = 5,
) -> dict[str, Any]:
    """Детальная сводка для /summary: top tasks, approvals, artifacts, molt, degraded."""
    data = get_system_status_summary()
    data["top_tasks"] = get_active_tasks(limit=tasks_limit)
    data["pending_approvals_list"] = get_pending_approvals(limit=approvals_limit)
    data["recent_artifacts_list"] = get_recent_artifacts(limit=artifacts_limit)
    data["runs_in_progress"] = get_runs_summary(limit=tasks_limit)
    return data
