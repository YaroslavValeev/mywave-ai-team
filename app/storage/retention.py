from datetime import datetime, timedelta

from app.storage.models import AuditEvent, Task


def run_retention_cleanup(session, retention_days: int) -> dict:
    """Удалить старые задачи и orphan audit events старше retention_days."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted_tasks = 0
    deleted_orphan_audits = 0

    old_tasks = session.query(Task).filter(Task.created_at < cutoff).all()
    for task in old_tasks:
        session.delete(task)
        deleted_tasks += 1

    orphan_audits = (
        session.query(AuditEvent)
        .filter(AuditEvent.task_id.is_(None), AuditEvent.created_at < cutoff)
        .all()
    )
    for event in orphan_audits:
        session.delete(event)
        deleted_orphan_audits += 1

    session.commit()
    return {
        "retention_days": retention_days,
        "cutoff": cutoff.isoformat(),
        "deleted_tasks": deleted_tasks,
        "deleted_orphan_audits": deleted_orphan_audits,
    }
