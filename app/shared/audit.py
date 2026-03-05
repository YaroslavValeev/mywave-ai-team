# app/shared/audit.py — Audit log + decision log (обёртка над storage)
from typing import Optional

# Используется через TaskRepository.add_audit_event и add_decision


def log_audit(repo, event_type: str, task_id: Optional[int] = None, payload: Optional[dict] = None):
    """Записать событие в audit log."""
    repo.add_audit_event(event_type=event_type, task_id=task_id, payload=payload)


def log_decision(repo, task_id: int, decision: str, rationale: Optional[str] = None, owner_approval: bool = False):
    """Записать решение в decision log."""
    repo.add_decision(task_id=task_id, decision=decision, rationale=rationale, owner_approval=owner_approval)
