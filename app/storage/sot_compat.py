# app/storage/sot_compat.py — Adapter layer (Phase 3): legacy Task ↔ SoT контракты.
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.storage.models import ExecutionEvent, Run, Task


def ensure_task_project_linked(session: Session, task: Task) -> Task:
    """
    Ленивый backfill: задачи без project_id получают default project.
    Идемпотентно; безопасно для старых строк до data-migration 004.
    """
    from app.storage.repositories import TaskRepository

    if task.project_id is not None:
        return task
    repo = TaskRepository(session)
    proj = repo._ensure_default_project()  # noqa: SLF001
    task.project_id = proj.id
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def task_sot_view(task: Task) -> dict[str, Any]:
    """Канонический срез для API/MCP (расширяемый без ломки legacy полей)."""
    return {
        "task_id": task.id,
        "project_id": task.project_id,
        "status": task.status,
        "domain": task.domain,
        "task_type": task.task_type,
        "criticality": task.criticality,
        "plan_or_execute": task.plan_or_execute,
        "version": task.version,
    }


def execution_event_to_public_dict(ev: ExecutionEvent) -> dict[str, Any]:
    """Формат ответа для execution_events (Phase 5 observability)."""
    return {
        "id": ev.id,
        "event_type": ev.event_type,
        "phase": ev.phase,
        "run_db_id": ev.run_id,
        "payload": ev.payload_json,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


def run_to_public_dict(run: Run) -> dict[str, Any]:
    """Единый формат ответа для Run (GET /api/tasks/{id}/runs и др.)."""
    return {
        "id": run.id,
        "run_id": run.run_id,
        "orchestrator": run.orchestrator,
        "source": run.source,
        "state": run.state,
        "phase": run.phase,
        "phase_label": run.phase_label,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "is_active": run.is_active,
        "result_status": run.result_status,
    }


AUDIT_TO_EXECUTION_HINT: dict[str, str] = {
    "pipeline_background_started": "orchestration_background_started",
    "pipeline_background_completed": "orchestration_background_completed",
    "pipeline_background_stopped": "orchestration_background_stopped",
    "pipeline_background_failed": "orchestration_background_failed",
}


def audit_event_execution_hint(event_type: str) -> Optional[str]:
    """Подсказка для маппинга audit → execution_events (без автозаписи)."""
    return AUDIT_TO_EXECUTION_HINT.get(event_type)
