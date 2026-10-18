import importlib.util
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

SOURCE = (
    Path(__file__).resolve().parents[2] / "scripts/server/recover_task35_20261018.py"
)
spec = importlib.util.spec_from_file_location("orphan35", SOURCE)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
NOW = datetime(2026, 10, 18, 12)


def snapshot(**changes):
    data = {
        "task_id": 35,
        "created_at": "2026-10-01T12:34:03.124363",
        "updated_at": "2026-10-01T12:34:03.124363",
        "status": "IN_PIPELINE",
        "runtime_active": False,
        "persisted_run_active": False,
    }
    return {**data, **changes}


def test_confirmed_orphan_is_recoverable_and_rework_is_idempotent():
    assert recovery.needs_recovery(snapshot(), NOW) is True
    assert recovery.needs_recovery(snapshot(status="REWORK"), NOW) is False


@pytest.mark.parametrize(
    "changes",
    [
        {"task_id": 36},
        {"created_at": "wrong"},
        {"runtime_active": True},
        {"runtime_active": None},
        {"persisted_run_active": True},
        {"persisted_run_active": None},
        {"status": "DONE"},
        {"updated_at": "2026-10-18T11:00:00"},
        {"updated_at": None},
    ],
)
def test_unconfirmed_or_active_work_is_never_changed(changes):
    with pytest.raises(RuntimeError):
        recovery.needs_recovery(snapshot(**changes), NOW)


def test_recovery_requires_the_explicit_task_gate(monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["recover", "--execute", "--owner-approved-task", "36"]
    )
    run = Mock()
    monkeypatch.setattr(recovery.subprocess, "run", run)
    with pytest.raises(SystemExit):
        recovery.main()
    run.assert_not_called()


@pytest.fixture
def worker_database(tmp_path, monkeypatch):
    import io
    import urllib.request
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    monkeypatch.syspath_prepend(str(SOURCE.parents[2]))
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("OWNER_API_KEY", "isolated_worker_key")
    from app.storage import models, repositories

    engine = sa.create_engine("sqlite:///" + str(tmp_path / "orphan.sqlite"))
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repositories, "get_session_factory", lambda: factory)
    with factory() as session:
        session.add(
            models.Task(
                id=35,
                owner_text="#TASK preserved input",
                summary="preserved summary",
                status="IN_PIPELINE",
                created_at=datetime(2026, 10, 1, 12, 34, 3, 124363),
                updated_at=datetime(2026, 10, 1, 12, 34, 3, 124363),
            )
        )
        session.commit()
    transaction_started = []
    sa.event.listen(
        engine, "begin", lambda connection: transaction_started.append(True)
    )

    def urlopen(request, timeout):
        assert (
            not transaction_started
        ), "HTTP callback while holding a database transaction"
        return io.BytesIO(b'{"runner":{"is_active":false}}')

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    yield factory, models
    engine.dispose()


@pytest.mark.parametrize("mode", ["check", "execute"])
def test_real_worker_persists_status_and_audit_atomically(
    worker_database, monkeypatch, capsys, mode
):
    import inspect
    import json

    factory, models = worker_database
    monkeypatch.setattr("sys.argv", ["worker", mode])
    code = recovery.WORKER.replace(
        "POLICY_SOURCE", inspect.getsource(recovery.needs_recovery)
    )
    exec(compile(code, "recovery-worker", "exec"), {})
    result = json.loads(capsys.readouterr().out)
    assert result["changed"] is (mode == "execute")
    with factory() as session:
        task = session.get(models.Task, 35)
        assert task.status == ("REWORK" if mode == "execute" else "IN_PIPELINE")
        assert task.summary == "preserved summary"
        assert task.owner_text == "#TASK preserved input"
        events = session.query(models.AuditEvent).all()
        assert len(events) == (1 if mode == "execute" else 0)
        if events:
            assert events[0].payload_json["status_after"] == "REWORK"


def test_worker_rolls_back_task_if_audit_insert_fails(worker_database, monkeypatch):
    import inspect
    from sqlalchemy.exc import IntegrityError

    factory, models = worker_database
    actual_event = models.AuditEvent
    monkeypatch.setattr(
        models, "AuditEvent", lambda **kwargs: actual_event(task_id=35, event_type=None)
    )
    monkeypatch.setattr("sys.argv", ["worker", "execute"])
    code = recovery.WORKER.replace(
        "POLICY_SOURCE", inspect.getsource(recovery.needs_recovery)
    )
    with pytest.raises(IntegrityError):
        exec(compile(code, "recovery-worker", "exec"), {})
    with factory() as session:
        assert session.get(models.Task, 35).status == "IN_PIPELINE"
        assert session.query(actual_event).count() == 0
