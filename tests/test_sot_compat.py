from app.storage.models import Task, TaskStatus
from app.storage.repositories import TaskRepository
from app.storage.sot_compat import (
    audit_event_execution_hint,
    run_to_public_dict,
    task_sot_view,
)


def test_get_task_backfills_missing_project_id(db_session):
    t = Task(owner_text="# TASK legacy null project", status=TaskStatus.NEW.value, project_id=None)
    db_session.add(t)
    db_session.commit()

    repo = TaskRepository(db_session)
    loaded = repo.get_task(t.id)
    assert loaded is not None
    assert loaded.project_id is not None


def test_task_sot_view_shape(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK sot view")
    view = task_sot_view(task)
    assert view["task_id"] == task.id
    assert view["project_id"] == task.project_id
    assert "status" in view


def test_run_to_public_dict_shape(db_session):
    from datetime import datetime

    from app.storage.models import Run

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK run dict")
    run = Run(
        run_id="abc123def0",
        task_id=task.id,
        orchestrator="orchestration_runtime",
        source="test",
        state="completed",
        phase="pipeline",
        phase_label="Pipeline",
        started_at=datetime.utcnow(),
        is_active=False,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    d = run_to_public_dict(run)
    assert d["run_id"] == "abc123def0"
    assert d["state"] == "completed"
    assert "started_at" in d


def test_audit_event_execution_hint():
    assert audit_event_execution_hint("pipeline_background_started") == "orchestration_background_started"
    assert audit_event_execution_hint("unknown") is None
