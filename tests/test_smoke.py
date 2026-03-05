# tests/test_smoke.py — smoke tests
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Проверка что модули импортируются."""
    from app.storage.models import Task, AuditEvent, Decision
    from app.config import get_routing, get_policy
    from app.shared.redaction import redact
    from app.shared.critical_flags import check_critical_execute
    assert Task is not None
    assert redact("test@mail.com") != "test@mail.com"
    assert check_critical_execute({"prod_deploy": True}) is True
    assert check_critical_execute({"prod_deploy": False}) is False


def test_redaction():
    """Проверка маскирования PII (HF-2)."""
    from app.shared.redaction import redact, scrub_secrets
    assert "***" in redact("+7 999 123-45-67")
    assert "***" in redact("user@example.com")
    assert "***" in redact("token=sk_abc123verylongkey")
    # scrub_secrets: ключи всегда маскируются
    assert "***" in scrub_secrets("api_key=sk_xxx123verylongsecretkey")


def test_triage():
    """Проверка triage."""
    from app.orchestrator.triage import run_triage
    r = run_triage("# TASK\nНазвание: Деплой сайта\nЦель: выкатить прод")
    assert "domain" in r
    assert r.get("plan_or_execute") in ("PLAN", "EXECUTE")
    assert r.get("domain") in ("PRODUCT_DEV", "MEDIA_OPS", "EVENTS", "GAME", "INFRA", "RND_EXTREME", "RUZA", "CLIENTOPS", "SPONSOR_PLATFORM", "AUTHORITY_CONTENT")


def test_create_task(db_session):
    """Создание задачи и запись в audit."""
    from app.storage.repositories import TaskRepository
    from app.shared.audit import log_audit
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK test")
    assert task.id is not None
    assert task.status == "NEW"
    log_audit(repo, "task_created", task_id=task.id, payload={"test": True})
    task2 = repo.get_task(task.id)
    assert task2 is not None


def test_health_no_auth():
    """GET /health без ключа → 200."""
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_api_tasks(db_session):
    """GET /tasks: без ключа 401, с ключом 200 (HF-1)."""
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/tasks")
    assert resp.status_code == 401
    key = os.environ.get("OWNER_API_KEY", "test_key_for_smoke")
    resp2 = client.get("/api/tasks", headers={"X-API-Key": key})
    assert resp2.status_code == 200
    assert isinstance(resp2.json(), list)
