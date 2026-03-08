# tests/test_api_auth.py — v0.2: 401 без X-API-Key, 200 с ключом
import os
import pytest
from fastapi.testclient import TestClient

from app.dashboard.app import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    key = os.environ.get("OWNER_API_KEY", "test_key_for_smoke")
    return {"X-API-Key": key}


def test_health_no_auth_required(client):
    """GET /health — без auth, 200."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_api_tasks_401_without_key(client, db_session):
    """GET /api/tasks без ключа → 401."""
    r = client.get("/api/tasks")
    assert r.status_code == 401


def test_api_tasks_200_with_key(client, auth_headers, db_session):
    """GET /api/tasks с ключом → 200."""
    r = client.get("/api/tasks", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_api_post_task_401(client):
    """POST /api/tasks без ключа → 401."""
    r = client.post("/api/tasks", json={"domain": "PRODUCT_DEV", "task_type": "general"})
    assert r.status_code == 401


def test_api_post_task_200(client, auth_headers, db_session):
    """POST /api/tasks с ключом → 200."""
    r = client.post("/api/tasks", json={"domain": "PRODUCT_DEV", "task_type": "general"}, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data.get("domain") == "PRODUCT_DEV"


def test_api_patch_task_401(client, db_session):
    """PATCH /api/tasks/{id} без ключа → 401."""
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK test")
    r = client.patch(f"/api/tasks/{task.id}", json={"status": "DONE"})
    assert r.status_code == 401


def test_api_pipeline_run_401(client, db_session):
    """POST /api/tasks/{id}/pipeline/run без ключа → 401."""
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK test")
    r = client.post(f"/api/tasks/{task.id}/pipeline/run")
    assert r.status_code == 401


def test_api_audit_on_request(client, auth_headers, db_session):
    """После /api/* запроса — audit_events содержит запись."""
    from app.storage.models import AuditEvent
    r = client.get("/api/tasks", headers=auth_headers)
    assert r.status_code == 200
    audits = db_session.query(AuditEvent).filter(AuditEvent.event_type == "api_request").all()
    assert len(audits) >= 1
    a = audits[-1]
    assert a.payload_json.get("route") == "/api/tasks"
    assert a.payload_json.get("status_code") == 200
    assert "latency_ms" in a.payload_json
