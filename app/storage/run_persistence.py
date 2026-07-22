"""Персистентность Run / ExecutionEvent при старте и завершении фоновой оркестрации."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _on_orchestration_lifecycle(event: str, task_id: int, run_id: str, state: dict) -> None:
    from app.storage.repositories import TaskRepository, get_session_factory

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        if event == "started":
            started_at = _parse_dt(state.get("started_at")) or datetime.utcnow()
            run = repo.create_run_record(
                task_id=task_id,
                run_id=run_id,
                source=state.get("source"),
                state=state.get("state") or "running",
                phase=state.get("phase"),
                phase_label=state.get("phase_label"),
                message=state.get("message"),
                current_step=state.get("current_step") or "",
                started_at=started_at,
                is_active=True,
            )
            repo.add_execution_event(
                task_id,
                run_db_id=run.id,
                event_type="run_started",
                phase=state.get("phase"),
                payload={"run_id": run_id, "source": state.get("source")},
            )
            return

        if event == "terminal":
            finished_at = _parse_dt(state.get("finished_at")) or datetime.utcnow()
            repo.update_run_terminal(
                run_id,
                state=state.get("state") or "completed",
                phase=state.get("phase"),
                phase_label=state.get("phase_label"),
                message=state.get("message"),
                current_step=state.get("current_step") or "",
                finished_at=finished_at,
                requested_stop_at=_parse_dt(state.get("requested_stop_at")),
                last_error=state.get("last_error") or None,
                result_status=state.get("result_status") or None,
                is_active=bool(state.get("is_active", False)),
            )
            db_run = repo.get_run_by_run_id(run_id)
            event_type = {
                "completed": "run_completed",
                "failed": "run_failed",
                "cancelled": "run_cancelled",
            }.get(state.get("state") or "", "run_terminal")
            repo.add_execution_event(
                task_id,
                run_db_id=db_run.id if db_run else None,
                event_type=event_type,
                phase=state.get("phase"),
                payload={
                    "run_id": run_id,
                    "state": state.get("state"),
                    "result_status": state.get("result_status"),
                    "last_error": state.get("last_error"),
                },
            )


_registered = False


def register_orchestration_run_persistence() -> None:
    global _registered
    if _registered:
        return
    _registered = True
    from app.orchestrator.runtime import register_run_lifecycle_listener

    register_run_lifecycle_listener(_on_orchestration_lifecycle)
