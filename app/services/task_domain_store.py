# app/services/task_domain_store.py — Phase 10.0: task domain metadata (compute on read baseline)
from __future__ import annotations

from typing import Any, Optional

from app.storage.repositories import get_session_factory, TaskRepository
from app.services.domain_triage import build_task_domain_metadata


def get_task_domain_metadata(task_id: int) -> Optional[dict[str, Any]]:
    """
    Получить domain metadata для задачи (compute on read).
    Загружает task по task_id, берёт owner_text, вызывает build_task_domain_metadata.
    """
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
    if not task:
        return None
    owner_text = getattr(task, "owner_text", None) or ""
    return build_task_domain_metadata(owner_text)
