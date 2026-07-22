# app/governance/owner_flow.py — единая точка owner gate после суда / оркестрации.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.repositories import TaskRepository


def on_orchestration_awaiting_owner(repo: TaskRepository, task_id: int, final_status: str) -> None:
    """
    Когда оркестрация переводит задачу в WAIT_OWNER, фиксируем pending Approval (SoT).
    Идемпотентно: повторный вызов не создаёт дубликат REQUESTED.
    """
    if final_status != "WAIT_OWNER":
        return
    repo.ensure_pending_owner_approval(task_id)
