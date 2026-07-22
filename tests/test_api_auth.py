# tests/test_api_auth.py — v0.2: 401 без X-API-Key, 200 с ключом
import pytest


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


def test_api_system_health_200_with_key(client, auth_headers, db_session):
    """GET /api/system/health с ключом → сводный health payload."""
    r = client.get("/api/system/health", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in {"ok", "warn", "error"}
    assert "database" in data["checks"]


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


def test_api_approve_sets_done_and_logs_decision(client, auth_headers, db_session):
    """POST /api/tasks/{id}/approve → DONE без PR и пишет audit/decision."""
    from app.storage.repositories import TaskRepository
    from app.storage.models import AuditEvent, Decision

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK написать smoke tests")
    repo.update_task(task.id, status="WAIT_OWNER", summary="Нужен owner decision")

    r = client.post(f"/api/tasks/{task.id}/approve", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "DONE"

    db_session.expire_all()
    updated = repo.get_task(task.id)
    assert updated.status == "DONE"
    assert "Owner утвердил результат." in (updated.summary or "")
    assert any(a.event_type == "OWNER_APPROVED" for a in db_session.query(AuditEvent).filter(AuditEvent.task_id == task.id).all())
    assert any(d.decision == "a" and d.owner_approval for d in db_session.query(Decision).filter(Decision.task_id == task.id).all())


def test_api_clarify_sets_need_info(client, auth_headers, db_session):
    """POST /api/tasks/{id}/clarify → NEED_INFO."""
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK нужно уточнение")
    repo.update_task(task.id, status="WAIT_OWNER", summary="Нужен owner decision")

    r = client.post(f"/api/tasks/{task.id}/clarify", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "NEED_INFO"
    db_session.expire_all()
    updated = repo.get_task(task.id)
    assert updated.status == "NEED_INFO"
    assert "Owner запросил уточнение." in (updated.summary or "")


def test_api_rework_reruns_orchestration(client, auth_headers, db_session):
    """POST /api/tasks/{id}/rework → повторный прогон и финальный статус."""
    from app.storage.repositories import TaskRepository
    from app.storage.models import Decision

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK написать тесты для API")
    repo.update_task(task.id, status="WAIT_OWNER", summary="Нужен owner decision")

    r = client.post(f"/api/tasks/{task.id}/rework", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["decision"] == "rework"
    assert data["status"] in {"DONE", "WAIT_OWNER"}
    db_session.expire_all()
    assert repo.get_task(task.id).report_path
    assert any(d.decision == "r" for d in db_session.query(Decision).filter(Decision.task_id == task.id).all())


def test_api_mark_merged_sets_done(client, auth_headers, db_session):
    """POST /api/tasks/{id}/merged → DONE."""
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK merge done")
    repo.update_task(task.id, status="APPROVED_WAIT_MERGE", pr_url="https://github.com/example/repo/pull/1")

    r = client.post(f"/api/tasks/{task.id}/merged", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "DONE"
    db_session.expire_all()
    updated = repo.get_task(task.id)
    assert updated.status == "DONE"
    assert "Merge подтверждён." in (updated.summary or "")
