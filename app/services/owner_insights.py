from __future__ import annotations

from datetime import datetime, timedelta, timezone
from collections import Counter
from typing import Any

from sqlalchemy import text

from app.services.owner_queries import get_system_status_summary
from app.storage.models import TaskStatus
from app.storage.repositories import get_session_factory, TaskRepository


def _to_utc(dt: datetime | str | None) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _project_key(task: Any) -> str:
    # Baseline grouping: domain -> task_type -> "general"
    return (getattr(task, "domain", None) or getattr(task, "task_type", None) or "general").strip() or "general"


def _is_recent(dt: datetime | None, since: datetime) -> bool:
    v = _to_utc(dt)
    return bool(v and v >= since)


def get_awaiting_decisions_summary(limit: int = 10) -> dict[str, Any]:
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    pending = [t for t in tasks if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    return {
        "pending_count": len(pending),
        "items": pending[:limit],
    }


def get_completed_recently_summary(limit: int = 10) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    completed = [t for t in tasks if t.status == TaskStatus.DONE.value and _is_recent(t.updated_at, since)]
    artifacts = [t for t in completed if t.report_path or t.summary]
    return {
        "completed_count": len(completed),
        "artifact_count": len(artifacts),
        "items": completed[:limit],
        "recent_artifacts": artifacts[:limit],
    }


def get_long_running_summary(limit: int = 10) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    waiting_threshold = timedelta(hours=24)
    active_threshold = timedelta(hours=6)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    items = []
    for t in tasks:
        updated = _to_utc(t.updated_at) or _to_utc(t.created_at)
        if not updated:
            continue
        age = now - updated
        if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value) and age >= waiting_threshold:
            items.append({"task": t, "reason": "waiting_owner_too_long", "age_hours": int(age.total_seconds() // 3600)})
        elif t.status in (TaskStatus.IN_PIPELINE.value, TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value) and age >= active_threshold:
            items.append({"task": t, "reason": "running_without_progress", "age_hours": int(age.total_seconds() // 3600)})
    return {"count": len(items), "items": items[:limit]}


def get_rework_signal_summary(limit: int = 10) -> dict[str, Any]:
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    repeated = [t for t in tasks if (t.rework_cycles or 0) >= 2 or t.status == TaskStatus.REWORK.value]
    repeated_sorted = sorted(repeated, key=lambda t: (t.rework_cycles or 0), reverse=True)
    return {"count": len(repeated_sorted), "items": repeated_sorted[:limit]}


def get_degraded_signal_summary(limit: int = 10) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    status = get_system_status_summary()
    Session = get_session_factory()
    with Session() as session:
        # heuristics by audit events in last 7 days
        events = session.execute(
            text("SELECT event_type, created_at, task_id FROM audit_events ORDER BY created_at DESC")
        ).fetchall()
    relevant = []
    for ev in events:
        created = _to_utc(ev.created_at)
        if not created or created < since:
            continue
        et = (ev.event_type or "").lower()
        if "error" in et or "degraded" in et or "rollback" in et:
            relevant.append({"event_type": ev.event_type, "task_id": ev.task_id, "created_at": created})
    return {
        "current_state": status.get("state", "OK"),
        "molt_ok": status.get("molt_ok", True),
        "events_count_7d": len(relevant),
        "events": relevant[:limit],
    }


def get_project_activity_summary(limit: int = 10) -> dict[str, Any]:
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    counter = Counter()
    for t in tasks:
        counter[_project_key(t)] += 1
    top = [{"project": k, "tasks_count": v} for k, v in counter.most_common(limit)]
    return {"projects_count": len(counter), "top_projects": top}


def get_blockers_summary(limit: int = 10) -> dict[str, Any]:
    awaiting = get_awaiting_decisions_summary(limit=limit)
    long_running = get_long_running_summary(limit=limit)
    degraded = get_degraded_signal_summary(limit=limit)
    items = []
    for t in awaiting["items"][:limit]:
        items.append({"kind": "awaiting_decision", "task": t})
    for i in long_running["items"][: max(0, limit - len(items))]:
        items.append({"kind": i["reason"], "task": i["task"], "age_hours": i.get("age_hours", 0)})
    return {
        "blockers_count": awaiting["pending_count"] + long_running["count"] + (1 if degraded["current_state"] == "DEGRADED" else 0),
        "degraded_now": degraded["current_state"] == "DEGRADED",
        "items": items[:limit],
    }


def get_weekly_digest(limit: int = 5) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
        decisions_count = session.execute(
            text("SELECT COUNT(*) FROM decisions WHERE created_at >= :since"),
            {"since": since},
        ).scalar() or 0
        rework_events_count = session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE event_type = 'OWNER_REWORK' AND created_at >= :since"),
            {"since": since},
        ).scalar() or 0
    completed_week = [t for t in tasks if t.status == TaskStatus.DONE.value and _is_recent(t.updated_at, since)]
    active = [t for t in tasks if t.status not in (TaskStatus.DONE.value, TaskStatus.ARCHIVED.value)]
    pending = [t for t in tasks if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    artifacts = [t for t in completed_week if t.report_path or t.summary]
    degraded = get_degraded_signal_summary(limit=limit)
    blockers = get_blockers_summary(limit=limit)
    rework = get_rework_signal_summary(limit=limit)
    projects = get_project_activity_summary(limit=3)
    return {
        "window_days": 7,
        "completed_count": len(completed_week),
        "approvals_count": int(decisions_count),
        "rework_count": int(rework_events_count),
        "pending_approvals_count": len(pending),
        "active_tasks_count": len(active),
        "degraded_events_count": degraded["events_count_7d"],
        "blockers_count": blockers["blockers_count"],
        "recent_artifacts_count": len(artifacts),
        "top_completed": completed_week[:limit],
        "top_blockers": blockers["items"][:limit],
        "project_activity": projects.get("top_projects", []),
        "rework_signals": rework.get("items", [])[:limit],
        "degraded_signals": degraded.get("events", [])[:limit],
        "owner_focus": (
            "Приоритет: решения по approvals и разбор long-running задач."
            if pending or blockers["blockers_count"] > 0
            else "Критичных блокеров нет, фокус на планирование следующих задач."
        ),
    }
