# tests/test_owner_decision_molt_hooks.py — API/Dashboard approve hooks call canonical bridge.
from unittest.mock import patch

import pytest


def test_apply_owner_decision_approve_calls_canonical_hooks(client, auth_headers, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="#TASK hook parity test")
    repo.update_task(task.id, status="WAIT_OWNER", summary="ready")
    db_session.commit()

    with patch("app.canonical_bridge.apply_owner_decision_hooks_if_enabled") as hook:
        r = client.post(f"/api/tasks/{task.id}/approve", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "DONE"
        assert hook.called
        args, kwargs = hook.call_args
        assert args[0] == task.id
        assert args[1] == "a"
        assert kwargs.get("terminal_on_approve") is True
