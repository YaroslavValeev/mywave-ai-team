from datetime import datetime, timedelta


def test_retention_cleanup_deletes_old_tasks_and_orphan_audits(db_session):
    """Retention cleanup удаляет старые задачи и orphan audit events."""
    from app.storage.models import AuditEvent, Task
    from app.storage.repositories import TaskRepository
    from app.storage.retention import run_retention_cleanup

    repo = TaskRepository(db_session)
    old_task = repo.create_task(owner_text="# TASK old")
    new_task = repo.create_task(owner_text="# TASK new")

    cutoff_time = datetime.utcnow() - timedelta(days=120)
    old_task.created_at = cutoff_time
    old_task.updated_at = cutoff_time
    new_task.created_at = datetime.utcnow()
    new_task.updated_at = datetime.utcnow()

    db_session.add(AuditEvent(event_type="orphan_old", task_id=None, payload_json={}, created_at=cutoff_time))
    db_session.add(AuditEvent(event_type="orphan_new", task_id=None, payload_json={}, created_at=datetime.utcnow()))
    db_session.commit()

    result = run_retention_cleanup(db_session, retention_days=90)

    remaining_tasks = db_session.query(Task).all()
    remaining_events = db_session.query(AuditEvent).all()

    assert result["deleted_tasks"] == 1
    assert result["deleted_orphan_audits"] == 1
    assert len(remaining_tasks) == 1
    assert remaining_tasks[0].id == new_task.id
    assert any(event.event_type == "orphan_new" for event in remaining_events)
