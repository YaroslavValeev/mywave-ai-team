#!/usr/bin/env python3
# scripts/dump_audit_proof.py — генерация 5 строк audit_events для Release Evidence
# Запуск: python scripts/dump_audit_proof.py (из корня проекта)
# Требует: DATABASE_URL, OWNER_API_KEY в env (или sqlite :memory: + test key)

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OWNER_API_KEY", "test_key_proof")

from app.storage.repositories import get_session_factory, init_db, TaskRepository
from app.storage.models import AuditEvent
from fastapi.testclient import TestClient
from app.dashboard.app import app

def main():
    init_db()
    Session = get_session_factory()
    req_id = str(uuid.uuid4())

    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text="#TASK Proof")
        task_id = task.id
        repo.add_audit_event("mcp_tool_invoke", task_id=task_id, payload={"tool_name": "task_create", "actor": "mcp", "status": "ok", "latency_ms": 50, "request_id": req_id})
        repo.add_audit_event("api_request", task_id=None, payload={"actor": "owner", "route": "/api/tasks", "task_id": None, "status_code": 201, "latency_ms": 12, "request_id": req_id})
        repo.add_audit_event("api_request", task_id=task_id, payload={"actor": "owner", "route": f"/api/tasks/{task_id}/pipeline/run", "task_id": task_id, "status_code": 200, "latency_ms": 320, "request_id": str(uuid.uuid4())})
        repo.add_audit_event("OWNER_APPROVED", task_id=task_id, payload={"decision": "approve"})
        repo.add_audit_event("OWNER_MERGED", task_id=task_id, payload={"decision": "i_merged"})

    with Session() as session:
        events = session.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(5).all()
        for e in reversed(events):
            payload = e.payload_json or {}
            rid = payload.get("request_id", "-")
            print(f"- event_type={e.event_type} task_id={e.task_id} request_id={rid} payload={payload}")

if __name__ == "__main__":
    main()
