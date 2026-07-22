import time

from fastapi.testclient import TestClient

from app.dashboard.app import app
from app.storage.models import Project
from app.storage.repositories import TaskRepository


def test_create_task_assigns_default_project(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK default project")
    assert task.project_id is not None
    proj = db_session.get(Project, task.project_id)
    assert proj is not None
    assert proj.slug == "default"


def test_owner_approval_creates_approval_row(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK approval")
    d = repo.add_decision(task.id, decision="approve", owner_approval=True)
    assert d.id is not None
    db_session.refresh(task)
    assert len(task.approvals) == 1
    assert task.approvals[0].status == "APPROVED"
    assert task.approvals[0].decision_id == d.id


def test_background_run_persisted_and_listed(db_session, monkeypatch):
    from app.dashboard import api_router

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK persist run")

    def fast_run(repo, task_id, source="api", control=None):
        if control:
            control.set_phase("pipeline", message="ok", current_step="PM")
        repo.update_task(task_id, status="WAIT_OWNER", summary="быстрый проход")
        return {"status": "WAIT_OWNER", "summary": "быстрый проход"}

    monkeypatch.setattr(api_router, "run_task_orchestration", fast_run)

    start_resp = client.post(f"/api/tasks/{task.id}/pipeline/start", headers=headers)
    assert start_resp.status_code == 200
    run_id = start_resp.json()["runner"]["run_id"]
    assert run_id

    for _ in range(40):
        rt = client.get(f"/api/tasks/{task.id}/runtime", headers=headers)
        if rt.json()["runner"]["state"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.05)

    runs_resp = client.get(f"/api/tasks/{task.id}/runs", headers=headers)
    assert runs_resp.status_code == 200
    payload = runs_resp.json()
    assert payload["task_id"] == task.id
    assert len(payload["runs"]) >= 1
    match = next((r for r in payload["runs"] if r["run_id"] == run_id), None)
    assert match is not None
    assert match["state"] in {"completed", "failed", "cancelled", "running"}
