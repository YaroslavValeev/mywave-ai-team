# app/services/project_queries.py — Phase 9.5: project-level queries (drill-down)
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Any

from app.services.owner_queries import get_system_status_summary
from app.storage.repositories import get_session_factory, TaskRepository
from app.storage.models import TaskStatus

FALLBACK_GROUP = "general"


def _project_key(task: Any) -> str:
    k = (getattr(task, "domain", None) or getattr(task, "task_type", None) or FALLBACK_GROUP)
    return (k or FALLBACK_GROUP).strip() or FALLBACK_GROUP


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _tasks_for_project(project_key: str) -> list[Any]:
    """Все задачи, принадлежащие проекту (project_key)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    return [t for t in tasks if _project_key(t) == project_key]


def list_projects(limit: int = 50) -> dict[str, Any]:
    """Список проектов с health и счётчиками."""
    now = datetime.now(timezone.utc)
    wait_threshold = now - timedelta(hours=24)
    progress_threshold = now - timedelta(hours=6)
    status = get_system_status_summary()
    degraded_now = status.get("state") == "DEGRADED"

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()

    by_project = defaultdict(lambda: {"pending": 0, "active": 0, "rework_signals": 0, "long_running": 0})
    for t in tasks:
        key = _project_key(t)
        if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value):
            by_project[key]["pending"] += 1
        if t.status not in (TaskStatus.DONE.value, TaskStatus.ARCHIVED.value):
            by_project[key]["active"] += 1
        if (getattr(t, "rework_cycles", 0) or 0) >= 2 or t.status == TaskStatus.REWORK.value:
            by_project[key]["rework_signals"] += 1
        updated = _to_utc(t.updated_at) or _to_utc(t.created_at)
        if updated:
            if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value) and updated < wait_threshold:
                by_project[key]["long_running"] += 1
            elif t.status in (TaskStatus.IN_PIPELINE.value, TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value) and updated < progress_threshold:
                by_project[key]["long_running"] += 1

    result = []
    for project, counts in by_project.items():
        p, a, rw, lr = counts["pending"], counts["active"], counts["rework_signals"], counts["long_running"]
        if p >= 2 or (degraded_now and a > 0) or (rw >= 2 or lr >= 2):
            status_str = "critical"
            reason = "Порог блокеров/rework/degraded превышен"
        elif p >= 1 or rw >= 1 or lr >= 1:
            status_str = "attention_needed"
            reason = "Есть pending / rework / long-running"
        else:
            status_str = "healthy"
            reason = "Нет критичных сигналов"
        item = {
            "project_key": project,
            "project_label": project,
            "status": status_str,
            "reason": reason,
            "active_count": a,
            "pending_count": p,
            "rework_signals": rw,
            "long_running": lr,
        }
        try:
            from app.services.project_domain_mapping import get_project_dominant_domain
            item["dominant_domain"] = get_project_dominant_domain(project)
        except Exception:
            item["dominant_domain"] = None
        result.append(item)
    result.sort(key=lambda x: (x["status"] == "critical", x["status"] == "attention_needed", -x["pending_count"]))
    return {"items": result[:limit], "count": len(result)}


def get_project_overview(project_key: str) -> dict[str, Any]:
    """Сводка по проекту: health + счётчики. Phase 10.3: + domain profile."""
    health = get_project_health(project_key)
    tasks = _tasks_for_project(project_key)
    active = [t for t in tasks if t.status not in (TaskStatus.DONE.value, TaskStatus.ARCHIVED.value)]
    pending = [t for t in tasks if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    with_artifact = [t for t in tasks if getattr(t, "report_path", None) or getattr(t, "summary", None)]
    domain_profile = None
    try:
        from app.services.project_domain_mapping import get_project_domain_profile
        domain_profile = get_project_domain_profile(project_key)
    except Exception:
        pass
    return {
        "project_key": project_key,
        "project_label": health.get("project_label", project_key),
        "health": health,
        "active_count": len(active),
        "pending_count": len(pending),
        "recent_artifacts_count": len(with_artifact),
        "domain_profile": domain_profile,
    }


def get_project_health(project_key: str) -> dict[str, Any]:
    """Health одного проекта."""
    now = datetime.now(timezone.utc)
    wait_threshold = now - timedelta(hours=24)
    progress_threshold = now - timedelta(hours=6)
    status = get_system_status_summary()
    degraded_now = status.get("state") == "DEGRADED"
    tasks = _tasks_for_project(project_key)
    pending = active = rework_signals = long_running = 0
    for t in tasks:
        if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value):
            pending += 1
        if t.status not in (TaskStatus.DONE.value, TaskStatus.ARCHIVED.value):
            active += 1
        if (getattr(t, "rework_cycles", 0) or 0) >= 2 or t.status == TaskStatus.REWORK.value:
            rework_signals += 1
        updated = _to_utc(t.updated_at) or _to_utc(t.created_at)
        if updated:
            if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value) and updated < wait_threshold:
                long_running += 1
            elif t.status in (TaskStatus.IN_PIPELINE.value, TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value) and updated < progress_threshold:
                long_running += 1
    if pending >= 2 or (degraded_now and active > 0) or (rework_signals >= 2 or long_running >= 2):
        status_str = "critical"
        reason = "Порог блокеров/rework/degraded превышен"
    elif pending >= 1 or rework_signals >= 1 or long_running >= 1:
        status_str = "attention_needed"
        reason = "Есть pending / rework / long-running"
    else:
        status_str = "healthy"
        reason = "Нет критичных сигналов"
    return {
        "project_key": project_key,
        "project_label": project_key,
        "status": status_str,
        "reason": reason,
        "active_count": active,
        "pending_count": pending,
        "rework_signals": rework_signals,
        "long_running": long_running,
    }


def get_project_tasks(project_key: str, limit: int = 20) -> dict[str, Any]:
    """Активные задачи проекта."""
    tasks = _tasks_for_project(project_key)
    active = [t for t in tasks if t.status not in (TaskStatus.DONE.value, TaskStatus.ARCHIVED.value)]
    active.sort(key=lambda t: (_to_utc(t.updated_at) or _to_utc(t.created_at) or _now_min()), reverse=True)
    return {"items": active[:limit], "count": len(active)}


def _now_min() -> datetime:
    return datetime.min.replace(tzinfo=timezone.utc)


def get_project_pending_approvals(project_key: str, limit: int = 20) -> dict[str, Any]:
    """Задачи проекта, ожидающие решения owner."""
    tasks = _tasks_for_project(project_key)
    pending = [t for t in tasks if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    return {"items": pending[:limit], "count": len(pending)}


def get_project_recent_artifacts(project_key: str, limit: int = 20) -> dict[str, Any]:
    """Недавние артефакты проекта (задачи с report_path/summary)."""
    tasks = _tasks_for_project(project_key)
    with_art = [t for t in tasks if getattr(t, "report_path", None) or getattr(t, "summary", None)]
    with_art.sort(key=lambda t: _to_utc(t.updated_at) or _to_utc(t.created_at) or _now_min(), reverse=True)
    items = []
    for t in with_art[:limit]:
        updated = _to_utc(t.updated_at) or _to_utc(t.created_at)
        items.append({
            "task_id": getattr(t, "id", None),
            "summary": (getattr(t, "summary", None) or "")[:200],
            "report_path": getattr(t, "report_path", None),
            "updated_at": updated.isoformat() if updated else None,
        })
    return {"items": items, "count": len(items)}


def get_project_risks(project_key: str, limit: int = 10) -> dict[str, Any]:
    """Риски по проекту: rework, long-running, pending backlog."""
    tasks = _tasks_for_project(project_key)
    now = datetime.now(timezone.utc)
    wait_threshold = now - timedelta(hours=24)
    progress_threshold = now - timedelta(hours=6)
    risks = []
    pending = [t for t in tasks if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    if len(pending) >= 2:
        risks.append({
            "risk_type": "approvals_backlog",
            "reason": f"Pending approvals в проекте: {len(pending)}",
            "suggested_action": "Разобрать approvals",
        })
    rework_tasks = [t for t in tasks if (getattr(t, "rework_cycles", 0) or 0) >= 2 or t.status == TaskStatus.REWORK.value]
    if rework_tasks:
        risks.append({
            "risk_type": "rework_accumulation",
            "reason": f"Rework по {len(rework_tasks)} задачам в проекте",
            "suggested_action": "Уточнить постановку / принять результат",
        })
    long_running = 0
    for t in tasks:
        updated = _to_utc(t.updated_at) or _to_utc(t.created_at)
        if not updated:
            continue
        if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value) and updated < wait_threshold:
            long_running += 1
        elif t.status in (TaskStatus.IN_PIPELINE.value, TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value) and updated < progress_threshold:
            long_running += 1
    if long_running > 0:
        risks.append({
            "risk_type": "long_running",
            "reason": f"Задачи без прогресса: {long_running}",
            "suggested_action": "Решить или отложить",
        })
    return {"items": risks[:limit], "count": len(risks)}


def get_project_decision_queue(project_key: str, limit: int = 10) -> dict[str, Any]:
    """Очередь решений по проекту: pending approvals + long-running + rework."""
    pending = get_project_pending_approvals(project_key, limit=limit * 2)
    queue = []
    for t in pending["items"]:
        queue.append({
            "task_id": getattr(t, "id", None),
            "reason": "Pending approval / decision",
            "priority": "high",
            "suggested_next_action": "Принять решение: approve / rework / clarify",
            "if_ignored": "Решения будут копиться",
        })
    tasks = _tasks_for_project(project_key)
    now = datetime.now(timezone.utc)
    wait_threshold = now - timedelta(hours=24)
    progress_threshold = now - timedelta(hours=6)
    seen = {q["task_id"] for q in queue}
    for t in tasks:
        if getattr(t, "id", None) in seen:
            continue
        updated = _to_utc(t.updated_at) or _to_utc(t.created_at)
        if not updated:
            continue
        if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value) and updated < wait_threshold:
            queue.append({
                "task_id": getattr(t, "id", None),
                "reason": "Long wait for owner",
                "priority": "medium",
                "suggested_next_action": "Решить или отложить",
                "if_ignored": "Задача останется в подвешенном состоянии",
            })
            seen.add(getattr(t, "id", None))
        elif t.status in (TaskStatus.IN_PIPELINE.value, TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value) and updated < progress_threshold:
            queue.append({
                "task_id": getattr(t, "id", None),
                "reason": "No progress (long-running)",
                "priority": "medium",
                "suggested_next_action": "Проверить блокеры",
                "if_ignored": "Backlog растёт",
            })
            seen.add(getattr(t, "id", None))
        if (getattr(t, "rework_cycles", 0) or 0) >= 2 and getattr(t, "id", None) not in seen:
            queue.append({
                "task_id": getattr(t, "id", None),
                "reason": f"Repeated rework (cycles={getattr(t, 'rework_cycles', 0)})",
                "priority": "medium",
                "suggested_next_action": "Уточнить постановку",
                "if_ignored": "Риск повторного rework",
            })
            seen.add(getattr(t, "id", None))
    return {"items": queue[:limit], "count": len(queue)}
