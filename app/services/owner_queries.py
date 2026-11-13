# app/services/owner_queries.py — Phase 9.0: read-only owner-facing queries
from __future__ import annotations

import os
from typing import Any, Optional
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from app.storage.repositories import get_session_factory, TaskRepository
from app.storage.models import TaskStatus

try:
    from app.canonical_bridge import get_canonical_state
except ImportError:
    def get_canonical_state(task_id: int | str) -> dict:
        return {}


def _molt_health_check() -> tuple[bool, str]:
    """При MOLT_TRANSPORT_MODE=http проверить /health. Возвращает (ok, message)."""
    if os.getenv("MOLT_TRANSPORT_MODE", "").lower() != "http":
        return True, "local/stub"
    base = (os.getenv("MOLT_HTTP_BASE_URL") or "").rstrip("/")
    if not base:
        return False, "HTTP mode but MOLT_HTTP_BASE_URL not set"
    try:
        with urlopen(f"{base}/health", timeout=5) as r:
            if r.status == 200:
                return True, "up"
    except (URLError, HTTPError, OSError) as e:
        return False, f"down ({e!s})"
    return False, "down"


def get_system_status_summary() -> dict[str, Any]:
    """Собрать сводку для /status: tasks, approvals, artifacts, molt, state."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        all_tasks = repo.get_all_tasks()

    active_statuses = {
        TaskStatus.NEW.value, TaskStatus.TRIAGED.value, TaskStatus.IN_PIPELINE.value,
        TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value,
        TaskStatus.WAIT_OWNER.value, TaskStatus.REWORK.value, TaskStatus.NEED_INFO.value,
        TaskStatus.APPROVED_WAIT_MERGE.value,
    }
    active_tasks = [t for t in all_tasks if t.status in active_statuses]
    pending_approvals = [t for t in all_tasks if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    recent_with_artifact = [t for t in all_tasks if (t.report_path or t.summary)][:10]

    molt_ok, molt_msg = _molt_health_check()
    transport_mode = os.getenv("MOLT_TRANSPORT_MODE", "local").lower()

    state = "OK"
    if transport_mode == "http" and not molt_ok:
        state = "DEGRADED"
    elif pending_approvals and not active_tasks:
        state = "Waiting approvals"
    elif pending_approvals:
        state = "OK"  # можно оставить OK или "Waiting approvals" — оставляем OK, approvals в счётчике

    return {
        "transport_mode": transport_mode,
        "molt_ok": molt_ok,
        "molt_message": molt_msg,
        "active_tasks_count": len(active_tasks),
        "pending_approvals_count": len(pending_approvals),
        "recent_artifacts_count": len(recent_with_artifact),
        "state": state,
        "active_tasks": active_tasks[:5],
        "pending_approvals": pending_approvals[:5],
        "recent_artifacts": recent_with_artifact[:5],
    }


def get_active_tasks(limit: int = 10) -> list:
    """Последние активные задачи (не DONE/ARCHIVED)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    active = {
        TaskStatus.NEW.value, TaskStatus.TRIAGED.value, TaskStatus.IN_PIPELINE.value,
        TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value,
        TaskStatus.WAIT_OWNER.value, TaskStatus.REWORK.value, TaskStatus.NEED_INFO.value,
        TaskStatus.APPROVED_WAIT_MERGE.value,
    }
    return [t for t in tasks if t.status in active][:limit]


def get_task_card(task_id: int) -> Optional[dict[str, Any]]:
    """Карточка задачи: task, canonical state (run_id, approval_id, status), domain_metadata (Phase 10.0)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
    if not task:
        return None
    state = get_canonical_state(task_id)
    try:
        from app.services.task_domain_store import get_task_domain_metadata
        domain_metadata = get_task_domain_metadata(task_id)
    except Exception:
        domain_metadata = None
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
        effective_domain_context = get_effective_domain_context(task_id, getattr(task, "owner_text", None))
    except Exception:
        effective_domain_context = None
    try:
        from app.services.agent_specializations import suggest_specialization
        spec_pipeline = suggest_specialization(task_id, "pipeline", getattr(task, "owner_text", None))
        specialization_context = {
            "pipeline": spec_pipeline.get("selected_specialization", {}).get("specialization_key"),
            "profile_name": spec_pipeline.get("profile_name"),
            "reason": spec_pipeline.get("selection_reason"),
            "fallback_used": spec_pipeline.get("fallback_used", False),
        }
    except Exception:
        specialization_context = None
    return {
        "task": task,
        "run_id": state.get("run_id"),
        "approval_id": state.get("approval_id"),
        "canonical_task_id": state.get("canonical_task_id"),
        "canonical_status": state.get("status"),
        "last_event": state.get("last_event"),
        "domain_metadata": domain_metadata,
        "effective_domain_context": effective_domain_context,
        "specialization_context": specialization_context,
    }


def get_pending_approvals(limit: int = 10) -> list:
    """Задачи, ожидающие решения owner (WAIT_OWNER, APPROVED_WAIT_MERGE)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    pending = [t for t in tasks if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    return pending[:limit]


def get_recent_artifacts(limit: int = 10) -> list:
    """Последние задачи с артефактами (report_path или summary)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    with_art = [t for t in tasks if t.report_path or t.summary]
    return with_art[:limit]


def get_runs_summary(limit: int = 10) -> list[dict[str, Any]]:
    """Задачи с «активным» run (не DONE/ARCHIVED и с run_id в canonical state)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    done_arch = {TaskStatus.DONE.value, TaskStatus.ARCHIVED.value}
    result = []
    for t in tasks:
        if t.status in done_arch:
            continue
        state = get_canonical_state(t.id)
        if state.get("run_id"):
            result.append({"task": t, "run_id": state["run_id"], "canonical_status": state.get("status")})
        if len(result) >= limit:
            break
    return result
