import asyncio


def test_api_run_task_orchestration_delegates_to_sync_run(db_session, monkeypatch):
    from app.dashboard.api import common as api_common
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK проверить делегирование")

    called = {"ok": False}

    def fake_sync(repo_arg, task_id_arg, *, source, control):
        called["ok"] = True
        assert task_id_arg == task.id
        assert source == "api"
        assert control is None
        return {"ok": True, "status": "DONE", "report_path": "x.md", "summary": "ok"}

    monkeypatch.setattr(api_common, "run_sync_orchestration", fake_sync)
    result = api_common.run_task_orchestration(repo, task.id, source="api")

    assert called["ok"] is True
    assert result["status"] == "DONE"


def test_telegram_run_orchestration_uses_sync_run(db_session, monkeypatch):
    from app.bot import handlers
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK проверить telegram путь")

    called = {"sync": False}
    sent = {"count": 0}

    def fake_sync(repo_arg, task_id_arg, *, source, control=None, summary_max_chars=None):
        called["sync"] = True
        assert task_id_arg == task.id
        assert source == "telegram"
        return {"ok": True, "status": "WAIT_OWNER", "report_path": "x.md", "summary": "need owner"}

    async def fake_send(*_args, **_kwargs):
        sent["count"] += 1
        return True

    monkeypatch.setattr(handlers, "run_sync_orchestration", fake_sync)
    monkeypatch.setattr(handlers, "send_with_retry", fake_send)

    class DummyBot:
        pass

    asyncio.run(handlers._run_orchestration(task.id, 12345, DummyBot()))

    assert called["sync"] is True
    assert sent["count"] >= 1
