# Запись итогов миссии в MemoryEntry (Smart Intake v1)
from __future__ import annotations

import logging
import os

from app.storage.repositories import TaskRepository

logger = logging.getLogger(__name__)


def write_task_memory_after_orchestration(repo: TaskRepository, task_id: int) -> None:
    """Фиксирует краткий снимок задачи для последующего intake (без дублей по содержанию — не делаем в v1)."""
    if os.getenv("INTAKE_MEMORY_WRITE", "true").strip().lower() not in {"1", "true", "yes"}:
        return
    task = repo.get_task(task_id)
    if not task:
        return
    pid = task.project_id or repo.get_default_project().id
    parts = [
        f"Миссия #{task_id}, статус={task.status}",
    ]
    if task.summary:
        parts.append("--- summary ---")
        parts.append((task.summary or "").strip()[:4000])
    if task.owner_text:
        parts.append("--- owner_text (фрагмент) ---")
        parts.append((task.owner_text or "").strip()[:2000])
    content = "\n".join(parts)[:8000]
    try:
        repo.add_memory_entry(
            project_id=pid,
            scope="task_outcome",
            content=content,
            task_id=task_id,
            source_ref=f"task:{task_id}",
        )
    except Exception as exc:
        logger.warning("INTAKE_MEMORY_WRITE failed task=%s: %s", task_id, exc)
