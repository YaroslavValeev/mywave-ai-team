from pathlib import Path

import pytest

from app.execution import ExecutionRequestError, execution_capabilities
from app.execution import service
from app.dashboard.api.common import apply_merge_confirmation, apply_owner_decision
from app.storage.repositories import TaskRepository


class _FakeRuntime:
    def __init__(self):
        self.started = None

    def snapshot(self, task_id):
        return {"task_id": task_id, "is_active": False}

    def start(self, task_id, *, source, target):
        self.started = {"task_id": task_id, "source": source, "target": target}
        return {"task_id": task_id, "state": "running", "is_active": True, "can_stop": True}


class _SynchronousRuntime:
    def snapshot(self, task_id):
        return {"task_id": task_id, "is_active": False}

    def start(self, task_id, *, source, target):
        class Control:
            def set_phase(self, phase, *, message="", current_step=None):
                self.phase = phase
                self.message = message
                self.current_step = current_step

            def check_cancelled(self):
                return None

        target(Control())
        return {"task_id": task_id, "state": "completed", "is_active": False, "can_stop": False}


def _configure_execution(repo, task_id: int, workspace: Path, patch_path: Path):
    repo.update_task(
        task_id,
        status="EXECUTION_READY",
        business_action_json={
            "execution_request": {
                "executor": "code_pr",
                "mode": "patch",
                "workspace_path": str(workspace),
                "patch_path": str(patch_path),
            }
        },
    )


def test_execution_requires_explicit_owner_approval(db_session, tmp_path, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Изменить код через PR")
    patch_path = tmp_path / "change.patch"
    patch_path.write_text("diff --git a/a b/a\n", encoding="utf-8")
    _configure_execution(repo, task.id, tmp_path, patch_path)
    monkeypatch.setenv("EXECUTION_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path))

    capabilities = execution_capabilities(repo.get_task(task.id), {"is_active": False})

    assert capabilities["configured"] is True
    assert capabilities["approved"] is False
    assert capabilities["can_start"] is False


def test_execution_rejects_patch_outside_artifacts(db_session, tmp_path, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Изменить код через PR")
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    artifacts.mkdir()
    patch_path = tmp_path / "outside.patch"
    patch_path.write_text("patch", encoding="utf-8")
    _configure_execution(repo, task.id, workspace, patch_path)
    repo.add_decision(task.id, decision="approve", owner_approval=True)
    monkeypatch.setenv("EXECUTION_ALLOWED_ROOTS", str(workspace))
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts))

    capabilities = execution_capabilities(repo.get_task(task.id), {"is_active": False})

    assert capabilities["configured"] is False
    assert capabilities["can_start"] is False
    assert "ARTIFACTS_DIR" in capabilities["reason"]


def test_start_execution_moves_task_to_executing_and_starts_background_job(
    db_session, tmp_path, monkeypatch
):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Изменить код через PR")
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    artifacts.mkdir()
    patch_path = artifacts / "approved.patch"
    patch_path.write_text("patch", encoding="utf-8")
    _configure_execution(repo, task.id, workspace, patch_path)
    repo.add_decision(task.id, decision="approve", owner_approval=True)
    monkeypatch.setenv("EXECUTION_ALLOWED_ROOTS", str(workspace))
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts))
    fake_runtime = _FakeRuntime()
    monkeypatch.setattr(service, "get_orchestration_runtime", lambda: fake_runtime)

    result = service.start_approved_execution(task.id)

    db_session.expire_all()
    updated = repo.get_task(task.id)
    assert result["status"] == "EXECUTING"
    assert updated.status == "EXECUTING"
    assert fake_runtime.started["source"] == "owner_approved_execution"
    assert any(event.event_type == "execution_started" for event in updated.audit_events)


def test_start_execution_surfaces_validation_reason(db_session, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Нет execution request")
    repo.update_task(task.id, status="EXECUTION_READY")
    repo.add_decision(task.id, decision="approve", owner_approval=True)
    monkeypatch.setattr(service, "get_orchestration_runtime", lambda: _FakeRuntime())

    with pytest.raises(ExecutionRequestError, match="execution_request"):
        service.start_approved_execution(task.id)


def test_canonical_owner_approved_execution_reaches_done(db_session, tmp_path, monkeypatch):
    repo = TaskRepository(db_session)
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    artifacts.mkdir()
    patch_path = artifacts / "approved.patch"
    patch_path.write_text("diff --git a/a b/a\n", encoding="utf-8")
    task = repo.create_task(
        owner_text="Реальная миссия: после approval подготовить PR и закрыть задачу.",
    )
    repo.update_task(
        task.id,
        status="WAIT_OWNER",
        summary="Команда завершила court и ждёт решения владельца.",
        business_action_json={
            "execution_request": {
                "executor": "code_pr",
                "mode": "patch",
                "workspace_path": str(workspace),
                "patch_path": str(patch_path),
            }
        },
    )
    monkeypatch.setenv("EXECUTION_ALLOWED_ROOTS", str(workspace))
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setattr(service, "get_orchestration_runtime", lambda: _SynchronousRuntime())

    async def _fake_pr_loop(*args, **kwargs):
        return {
            "success": True,
            "pr_url": "https://github.com/example/mywave/pull/1",
            "commit_sha": "abc123",
            "ci_url": "https://github.com/example/mywave/actions/runs/1",
            "error": "",
            "evidence": ["pytest passed"],
        }

    monkeypatch.setattr(service, "run_pr_loop", _fake_pr_loop)

    approved = apply_owner_decision(repo, task.id, "approve", source="test")
    assert approved["status"] == "EXECUTION_READY"

    started = service.start_approved_execution(task.id)
    assert started["status"] == "EXECUTING"
    db_session.expire_all()
    after_execution = repo.get_task(task.id)
    assert after_execution.status == "APPROVED_WAIT_MERGE"
    assert after_execution.pr_url == "https://github.com/example/mywave/pull/1"

    merged = apply_merge_confirmation(repo, task.id, source="test")
    assert merged["status"] == "DONE"
    db_session.expire_all()
    done = repo.get_task(task.id)
    events = [event.event_type for event in done.audit_events]
    assert done.status == "DONE"
    assert "OWNER_APPROVED" in events
    assert "execution_started" in events
    assert "validation_done" in events
    assert "OWNER_MERGED" in events
