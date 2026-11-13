# app/services/action_audit.py — Phase 9.8: action center audit trail
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.storage.repositories import TaskRepository


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_action(
    repo: TaskRepository,
    action_id: str,
    action_name: str,
    role: str,
    actor: str,
    status: str,
    started_at: str,
    finished_at: str,
    result_summary: str,
    context: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> None:
    """Записать выполнение действия в audit_events (event_type=action_center)."""
    payload = {
        "action_id": action_id,
        "action_name": action_name,
        "role": role,
        "actor": actor,
        "context": context,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "result_summary": (result_summary or "")[:500],
        "error_message": (error_message or "")[:500] if error_message else None,
    }
    repo.add_audit_event(event_type="action_center", task_id=None, payload=payload)
