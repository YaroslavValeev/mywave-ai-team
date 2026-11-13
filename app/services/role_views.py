# app/services/role_views.py — Phase 9.7: role-scoped view aggregation (read-only)
from __future__ import annotations

from typing import Any

from app.services.owner_dashboard import (
    get_dashboard_overview,
    get_dashboard_next_actions,
    get_dashboard_blockers,
    get_dashboard_decision_queue,
    get_dashboard_project_health,
    get_dashboard_recent_artifacts,
    get_dashboard_digest_preview,
)
from app.services.owner_queries import (
    get_system_status_summary,
    get_active_tasks,
    get_pending_approvals,
    get_recent_artifacts,
)
from app.services.owner_insights import (
    get_blockers_summary,
    get_long_running_summary,
    get_awaiting_decisions_summary,
)
from app.services.owner_recommendations import get_decision_queue
from app.services.role_domain_recommendations import (
    get_owner_domain_recommendations,
    get_operator_domain_recommendations,
    get_executor_domain_recommendations,
    get_reviewer_domain_recommendations,
)
from app.services.collaboration_flows import get_role_collaboration_summary


def get_owner_view(limit_next: int = 5, limit_blockers: int = 10, limit_queue: int = 10,
                   limit_health: int = 10, limit_artifacts: int = 10) -> dict[str, Any]:
    """Полная картина для owner: overview, next actions, blockers, decision queue, health, artifacts, digest."""
    try:
        overview = get_dashboard_overview()
        next_actions = get_dashboard_next_actions(limit=limit_next)
        blockers = get_dashboard_blockers(limit=limit_blockers)
        decision_queue = get_dashboard_decision_queue(limit=limit_queue)
        project_health = get_dashboard_project_health(limit=limit_health)
        recent_artifacts = get_dashboard_recent_artifacts(limit=limit_artifacts)
        digest = get_dashboard_digest_preview()
    except Exception:
        overview = {"state": "Unknown", "transport_mode": "?", "molt_ok": False, "molt_message": "unavailable",
                    "active_tasks_count": 0, "pending_approvals_count": 0, "recent_artifacts_count": 0}
        next_actions = {"items": [], "count": 0}
        blockers = {"blockers_count": 0, "items": []}
        decision_queue = {"items": [], "count": 0}
        project_health = {"items": [], "count": 0}
        recent_artifacts = {"items": [], "count": 0}
        digest = {"weekly": {}, "monthly": {}}
    domain_rec = {}
    try:
        domain_rec = get_owner_domain_recommendations(limit_domains=5)
    except Exception:
        pass
    collaboration_summary = {}
    try:
        collaboration_summary = get_role_collaboration_summary("owner")
    except Exception:
        pass
    return {
        "overview": overview,
        "next_actions": next_actions,
        "blockers": blockers,
        "decision_queue": decision_queue,
        "project_health": project_health,
        "recent_artifacts": recent_artifacts,
        "digest_preview": digest,
        "domain_recommendations": domain_rec,
        "collaboration_summary": collaboration_summary,
    }


def get_operator_view(limit_blockers: int = 10, limit_long_running: int = 10) -> dict[str, Any]:
    """Runtime + degraded + stuck/blockers для operator."""
    try:
        status = get_system_status_summary()
        blockers = get_blockers_summary(limit=limit_blockers)
        long_running = get_long_running_summary(limit=limit_long_running)
    except Exception:
        status = {"transport_mode": "?", "molt_ok": False, "molt_message": "unavailable", "state": "Unknown",
                  "active_tasks_count": 0, "pending_approvals_count": 0}
        blockers = {"blockers_count": 0, "degraded_now": False, "items": []}
        long_running = {"count": 0, "items": []}
    domain_rec = {}
    try:
        domain_rec = get_operator_domain_recommendations(limit_domains=5)
    except Exception:
        pass
    collaboration_summary = {}
    try:
        collaboration_summary = get_role_collaboration_summary("operator")
    except Exception:
        pass
    return {
        "runtime": {
            "transport_mode": status.get("transport_mode", "?"),
            "molt_ok": status.get("molt_ok", False),
            "molt_message": status.get("molt_message", "n/a"),
            "state": status.get("state", "Unknown"),
            "active_tasks_count": status.get("active_tasks_count", 0),
        },
        "blockers": blockers,
        "long_running": long_running,
        "domain_recommendations": domain_rec,
        "collaboration_summary": collaboration_summary,
    }


def get_executor_view(limit_tasks: int = 10, limit_artifacts: int = 10, limit_blockers: int = 5) -> dict[str, Any]:
    """Active tasks, recent artifacts, blockers для executor."""
    try:
        active_tasks = get_active_tasks(limit=limit_tasks)
        recent_artifacts = get_recent_artifacts(limit=limit_artifacts)
        blockers = get_blockers_summary(limit=limit_blockers)
    except Exception:
        active_tasks = []
        recent_artifacts = []
        blockers = {"blockers_count": 0, "items": []}
    domain_rec = {}
    try:
        domain_rec = get_executor_domain_recommendations(limit_domains=5)
    except Exception:
        pass
    collaboration_summary = {}
    try:
        collaboration_summary = get_role_collaboration_summary("executor")
    except Exception:
        pass
    return {
        "active_tasks": active_tasks,
        "recent_artifacts": recent_artifacts,
        "blockers": blockers,
        "domain_recommendations": domain_rec,
        "collaboration_summary": collaboration_summary,
    }


def get_reviewer_view(limit_approvals: int = 10, limit_queue: int = 10) -> dict[str, Any]:
    """Pending approvals и decision queue для reviewer."""
    try:
        pending = get_pending_approvals(limit=limit_approvals)
        awaiting = get_awaiting_decisions_summary(limit=limit_approvals)
        queue = get_decision_queue(limit=limit_queue)
    except Exception:
        pending = []
        awaiting = {"pending_count": 0, "items": []}
        queue = {"items": [], "count": 0}
    domain_rec = {}
    try:
        domain_rec = get_reviewer_domain_recommendations(limit_domains=5)
    except Exception:
        pass
    collaboration_summary = {}
    try:
        collaboration_summary = get_role_collaboration_summary("reviewer")
    except Exception:
        pass
    return {
        "pending_approvals": pending,
        "awaiting_decisions": awaiting,
        "decision_queue": queue,
        "domain_recommendations": domain_rec,
        "collaboration_summary": collaboration_summary,
    }
