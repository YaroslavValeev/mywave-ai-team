# app/presenters/owner_dashboard_presenters.py — Phase 9.4: view-models for owner dashboard (web)
from __future__ import annotations

from typing import Any


def present_dashboard_overview(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для header/status: только поля для отображения + status_cue."""
    state = raw.get("state", "OK")
    molt_ok = raw.get("molt_ok", True)
    pending = raw.get("pending_approvals_count", 0)
    if state == "DEGRADED" or (isinstance(state, str) and "down" in state.lower()):
        status_cue = "DEGRADED"
    elif not molt_ok:
        status_cue = "HTTP runtime down"
    elif pending > 0:
        status_cue = "Pending approvals"
    elif pending == 0 and raw.get("active_tasks_count", 0) > 0:
        status_cue = "OK"
    else:
        status_cue = "OK" if state == "OK" else (state or "OK")
    return {
        "state": state,
        "transport_mode": raw.get("transport_mode", "?"),
        "molt_ok": molt_ok,
        "molt_message": raw.get("molt_message", ""),
        "active_tasks_count": raw.get("active_tasks_count", 0),
        "pending_approvals_count": pending,
        "recent_artifacts_count": raw.get("recent_artifacts_count", 0),
        "status_cue": status_cue,
    }


def present_dashboard_next_actions(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для блока next actions: список с полями для шаблона. Phase 11.7: + top_intervention_headline."""
    items = raw.get("items", [])
    out = {
        "items": [
            {
                "action_type": a.get("action_type", ""),
                "task_id": a.get("task_id"),
                "reason": a.get("reason", ""),
                "priority": a.get("priority", ""),
                "suggested_action": a.get("suggested_action", ""),
                "if_deferred": a.get("if_deferred"),
            }
            for a in items
        ],
        "count": raw.get("count", len(items)),
    }
    if raw.get("top_intervention_headline"):
        out["top_intervention_headline"] = raw["top_intervention_headline"]
    if raw.get("preferred_intervention_ref"):
        out["preferred_intervention_ref"] = raw["preferred_intervention_ref"]
    return out


def present_dashboard_blockers(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для blockers: task_id, summary, kind."""
    items = raw.get("items", [])
    out = []
    for i in items:
        task = i.get("task") if isinstance(i, dict) else None
        if task is not None:
            out.append({
                "task_id": getattr(task, "id", None),
                "summary": (getattr(task, "owner_text", None) or getattr(task, "summary", None) or "")[:150],
                "kind": i.get("kind", "blocker"),
            })
        elif isinstance(i, dict) and "task_id" in i:
            out.append({
                "task_id": i.get("task_id"),
                "summary": (i.get("summary") or "")[:150],
                "kind": i.get("kind", "blocker"),
            })
    return {"blockers_count": raw.get("blockers_count", len(out)), "items": out}


def present_dashboard_decision_queue(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для decision queue."""
    items = raw.get("items", [])
    return {
        "items": [
            {
                "task_id": q.get("task_id"),
                "reason": q.get("reason", ""),
                "priority": q.get("priority", ""),
                "suggested_next_action": q.get("suggested_next_action", ""),
                "if_ignored": q.get("if_ignored", ""),
            }
            for q in items
        ],
        "count": raw.get("count", len(items)),
    }


def present_dashboard_project_health(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для project health: project, status, reason, counts."""
    items = raw.get("items", [])
    return {
        "items": [
            {
                "project": h.get("project", ""),
                "status": h.get("status", "healthy"),
                "reason": h.get("reason", ""),
                "active_count": h.get("active_count", 0),
                "pending_count": h.get("pending_count", 0),
            }
            for h in items
        ],
        "count": raw.get("count", len(items)),
    }


def present_dashboard_recent_artifacts(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для recent artifacts (уже сериализованы в owner_dashboard)."""
    items = raw.get("items", [])
    return {"items": list(items), "count": raw.get("count", len(items))}


def present_dashboard_digest_preview(raw: dict[str, Any]) -> dict[str, Any]:
    """View-model для weekly + monthly digest previews."""
    weekly = raw.get("weekly", {})
    monthly = raw.get("monthly", {})
    return {
        "weekly": {
            "window_days": weekly.get("window_days", 7),
            "completed_count": weekly.get("completed_count", 0),
            "pending_approvals_count": weekly.get("pending_approvals_count", 0),
            "blockers_count": weekly.get("blockers_count", 0),
            "key_risks": weekly.get("key_risks", [])[:5],
            "needs_decision_count": len(weekly.get("needs_decision", [])),
            "next_week_priorities_count": len(weekly.get("next_week_priorities", [])),
            "owner_focus": weekly.get("owner_focus", ""),
        },
        "monthly": {
            "window_days": monthly.get("window_days", 30),
            "completed_count": monthly.get("completed_count", 0),
            "active_count": monthly.get("active_count", 0),
            "pending_approvals_count": monthly.get("pending_approvals_count", 0),
            "top_recommendations_count": len(monthly.get("top_recommendations", [])),
        },
    }
