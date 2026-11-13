# app/services/owner_dashboard.py — Phase 9.4: aggregation layer for owner dashboard (read-only)
from __future__ import annotations

from typing import Any

from app.services.owner_queries import (
    get_system_status_summary,
    get_recent_artifacts,
)
from app.services.owner_insights import get_blockers_summary
from app.services.owner_recommendations import (
    get_next_actions,
    get_decision_queue,
    get_project_health_summary,
    get_strategic_weekly_digest,
    get_monthly_digest_baseline,
)
from app.owner_summary import build_detailed_summary


def get_dashboard_overview() -> dict[str, Any]:
    """Header + system status для dashboard. Source: get_system_status_summary."""
    try:
        data = get_system_status_summary()
        return {
            "state": data.get("state", "OK"),
            "transport_mode": data.get("transport_mode", "local"),
            "molt_ok": data.get("molt_ok", True),
            "molt_message": data.get("molt_message", "n/a"),
            "active_tasks_count": data.get("active_tasks_count", 0),
            "pending_approvals_count": data.get("pending_approvals_count", 0),
            "recent_artifacts_count": data.get("recent_artifacts_count", 0),
        }
    except Exception:
        return {
            "state": "Unknown",
            "transport_mode": "?",
            "molt_ok": False,
            "molt_message": "unavailable",
            "active_tasks_count": 0,
            "pending_approvals_count": 0,
            "recent_artifacts_count": 0,
        }


def get_dashboard_next_actions(limit: int = 5) -> dict[str, Any]:
    """Next actions block. Phase 11.7/12.0: + top_intervention_headline from adaptive decision support."""
    try:
        data = get_next_actions(limit=limit)
        try:
            from app.services.adaptive_decision_support import get_portfolio_decision_support
            ads = get_portfolio_decision_support(window_days=30)
            if ads.get("top_problem"):
                data["top_intervention_headline"] = ads.get("top_problem", "")[:120]
                if ads.get("safe_action_available") and ads.get("safe_action_key"):
                    data["top_intervention_headline"] += f" → /do {ads['safe_action_key']}"
            data["preferred_intervention_ref"] = "/owner/interventions"
        except Exception:
            try:
                from app.services.intervention_planning import get_portfolio_intervention_plan
                plan = get_portfolio_intervention_plan(window_days=30)
                do_now = plan.get("do_now")
                if do_now:
                    data["top_intervention_headline"] = do_now.get("reason", "")[:120]
                    data["preferred_intervention_ref"] = "/owner/interventions"
            except Exception:
                pass
        return data
    except Exception:
        return {"items": [], "count": 0}


def get_dashboard_blockers(limit: int = 10) -> dict[str, Any]:
    """Blockers block. Source: owner_insights.get_blockers_summary."""
    try:
        return get_blockers_summary(limit=limit)
    except Exception:
        return {"blockers_count": 0, "items": []}


def get_dashboard_decision_queue(limit: int = 10) -> dict[str, Any]:
    """Decision queue block. Source: owner_recommendations.get_decision_queue."""
    try:
        return get_decision_queue(limit=limit)
    except Exception:
        return {"items": [], "count": 0}


def get_dashboard_project_health(limit: int = 10) -> dict[str, Any]:
    """Project health block. Source: owner_recommendations.get_project_health_summary."""
    try:
        return get_project_health_summary(limit=limit)
    except Exception:
        return {"items": [], "count": 0}


def get_dashboard_recent_artifacts(limit: int = 10) -> dict[str, Any]:
    """Recent artifacts. Source: owner_queries.get_recent_artifacts."""
    try:
        artifacts = get_recent_artifacts(limit=limit)
        items = []
        for t in (artifacts or [])[:limit]:
            updated = getattr(t, "updated_at", None)
            items.append({
                "task_id": getattr(t, "id", None),
                "summary": (getattr(t, "summary", None) or "")[:200],
                "report_path": getattr(t, "report_path", None),
                "updated_at": updated.isoformat() if updated else None,
            })
        return {"items": items, "count": len(items)}
    except Exception:
        return {"items": [], "count": 0}


def get_dashboard_operational_summary() -> dict[str, Any]:
    """Operational summary (как /summary). Source: build_detailed_summary."""
    try:
        return build_detailed_summary(tasks_limit=5, approvals_limit=5, artifacts_limit=5)
    except Exception:
        return {
            "state": "Unknown",
            "transport_mode": "?",
            "molt_ok": False,
            "top_tasks": [],
            "pending_approvals_list": [],
            "recent_artifacts_list": [],
            "runs_in_progress": [],
        }


def get_dashboard_digest_preview() -> dict[str, Any]:
    """Weekly + monthly digest previews в одном объекте."""
    try:
        weekly = get_strategic_weekly_digest()
    except Exception:
        weekly = {"window_days": 7, "completed_count": 0, "key_risks": [], "needs_decision": [], "next_week_priorities": [], "owner_focus": ""}
    try:
        monthly = get_monthly_digest_baseline()
    except Exception:
        monthly = {"window_days": 30, "completed_count": 0, "active_count": 0, "pending_approvals_count": 0, "top_recommendations": []}
    return {"weekly": weekly, "monthly": monthly}
