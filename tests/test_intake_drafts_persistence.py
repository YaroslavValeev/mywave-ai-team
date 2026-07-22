# Persistent Smart Intake drafts (DB-backed, survive bot restart)
from datetime import datetime, timedelta

import pytest

from app.storage.models import IntakeDraft
from app.storage.repositories import TaskRepository


def test_put_peek_pop_intake_draft(db_session):
    repo = TaskRepository(db_session)
    pid = repo.put_intake_draft({"kind": "create", "brief": {"title": "T"}}, ttl_sec=900)
    assert len(pid) == 8

    peeked = repo.peek_intake_draft(pid)
    assert peeked is not None
    assert peeked["kind"] == "create"
    assert peeked["brief"]["title"] == "T"

    popped = repo.pop_intake_draft(pid)
    assert popped is not None
    assert popped["kind"] == "create"
    assert repo.peek_intake_draft(pid) is None


def test_intake_draft_survives_new_session(db_session):
    """Симуляция рестарта бота: новая сессия читает тот же draft_id."""
    repo = TaskRepository(db_session)
    pid = repo.put_intake_draft({"kind": "attach", "task_id": 7, "block": "ctx"}, ttl_sec=900)
    db_session.commit()

    from app.storage.repositories import get_session_factory

    Session = get_session_factory()
    with Session() as session2:
        repo2 = TaskRepository(session2)
        peeked = repo2.peek_intake_draft(pid)
        assert peeked is not None
        assert peeked["task_id"] == 7


def test_intake_draft_expired_returns_none(db_session):
    repo = TaskRepository(db_session)
    pid = repo.put_intake_draft({"kind": "create"}, ttl_sec=900)
    row = db_session.query(IntakeDraft).filter(IntakeDraft.draft_id == pid).first()
    row.expires_at = datetime.utcnow() - timedelta(seconds=10)
    db_session.commit()

    assert repo.peek_intake_draft(pid) is None
    assert repo.pop_intake_draft(pid) is None


def test_purge_expired_intake_drafts(db_session):
    repo = TaskRepository(db_session)
    pid = repo.put_intake_draft({"kind": "create"}, ttl_sec=900)
    row = db_session.query(IntakeDraft).filter(IntakeDraft.draft_id == pid).first()
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    n = repo.purge_expired_intake_drafts()
    assert n >= 1
    assert db_session.query(IntakeDraft).filter(IntakeDraft.draft_id == pid).first() is None


def test_handlers_pending_helpers_use_db(db_session, monkeypatch):
    """Регрессия: _pending_* в handlers.py ходят в БД, не в память процесса."""
    from contextlib import contextmanager
    from app.bot import handlers

    @contextmanager
    def _session_ctx():
        yield db_session

    class _Factory:
        def __call__(self):
            return _session_ctx()

    monkeypatch.setattr(handlers, "get_session_factory", lambda: _Factory())

    pid = handlers._pending_put({"kind": "create", "brief": {"title": "H"}})
    assert handlers._pending_peek(pid) is not None
    popped = handlers._pending_pop(pid)
    assert popped["brief"]["title"] == "H"
