# Фасад: создание сущностей с выдачей ID и делегированием в репозитории.
# Вызывается слоями (Product, Governance, Runtime); storage передаётся извне (DI).
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from shared_core.ids import (
    TaskIdFactory,
    RunIdFactory,
    DecisionIdFactory,
    ApprovalIdFactory,
    ArtifactIdFactory,
    MemoryIdFactory,
    EventIdFactory,
    ProjectIdFactory,
)
from shared_core.protocols import StorageProtocol


def create_task(storage: StorageProtocol, data: dict[str, Any]) -> dict[str, Any]:
    """Создаёт Task с task_id из shared-core. Обязательные поля: project_id, title, description, priority, origin_channel."""
    task_id = TaskIdFactory.create()
    now = datetime.utcnow()
    payload = {
        "task_id": task_id,
        "status": "new",
        "created_at": now,
        "updated_at": now,
        **data,
    }
    storage.tasks.create(payload)
    return payload


def create_run(storage: StorageProtocol, task_id: str, orchestrator: str, data: Optional[dict] = None) -> dict[str, Any]:
    """Создаёт Run с run_id из shared-core. Вызывается только от имени Molt."""
    run_id = RunIdFactory.create()
    now = datetime.utcnow()
    payload = {
        "run_id": run_id,
        "task_id": task_id,
        "orchestrator": orchestrator,
        "status": "created",
        "started_at": now,
        **(data or {}),
    }
    storage.runs.create(payload)
    return payload


def create_decision(
    storage: StorageProtocol,
    task_id: str,
    decision_type: str,
    decision_value: str,
    created_by: str,
    data: Optional[dict] = None,
) -> dict[str, Any]:
    """Создаёт Decision с decision_id из shared-core. Вызывается Governance."""
    decision_id = DecisionIdFactory.create()
    now = datetime.utcnow()
    payload = {
        "decision_id": decision_id,
        "task_id": task_id,
        "decision_type": decision_type,
        "decision_value": decision_value,
        "created_at": now,
        "created_by": created_by,
        **(data or {}),
    }
    storage.decisions.create(payload)
    return payload


def create_approval(
    storage: StorageProtocol,
    task_id: str,
    scope: str,
    data: Optional[dict] = None,
) -> dict[str, Any]:
    """Создаёт Approval со status=requested. Scope должен быть из shared-policy approval_required_actions."""
    approval_id = ApprovalIdFactory.create()
    now = datetime.utcnow()
    payload = {
        "approval_id": approval_id,
        "task_id": task_id,
        "scope": scope,
        "status": "requested",
        "requested_at": now,
        **(data or {}),
    }
    storage.approvals.create(payload)
    return payload


def create_artifact(
    storage: StorageProtocol,
    task_id: str,
    artifact_type: str,
    storage_uri: str,
    data: Optional[dict] = None,
) -> dict[str, Any]:
    """Создаёт Artifact. Вызывается Runtime или Governance."""
    artifact_id = ArtifactIdFactory.create()
    now = datetime.utcnow()
    payload = {
        "artifact_id": artifact_id,
        "task_id": task_id,
        "artifact_type": artifact_type,
        "storage_uri": storage_uri,
        "created_at": now,
        **(data or {}),
    }
    storage.artifacts.create(payload)
    return payload


def upsert_memory(storage: StorageProtocol, data: dict[str, Any]) -> dict[str, Any]:
    """Создаёт или обновляет MemoryEntry. memory_id выдаётся при создании новой записи."""
    now = datetime.utcnow()
    if "memory_id" not in data or not data["memory_id"]:
        data = {**data, "memory_id": MemoryIdFactory.create(), "updated_at": now}
    else:
        data = {**data, "updated_at": now}
    storage.memory.upsert(data)
    return data


def append_event(storage: StorageProtocol, run_id: str, event_type: str, data: Optional[dict] = None) -> dict[str, Any]:
    """Добавляет ExecutionEvent. Вызывается только Runtime. data идёт в колонку payload (JSON)."""
    event_id = EventIdFactory.create()
    now = datetime.utcnow()
    payload = {
        "event_id": event_id,
        "run_id": run_id,
        "event_type": event_type,
        "timestamp": now,
        "payload": data or {},
    }
    storage.events.append(payload)
    return payload


def create_project(storage: StorageProtocol, data: dict[str, Any]) -> dict[str, Any]:
    """Создаёт Project с project_id из shared-core."""
    project_id = ProjectIdFactory.create()
    now = datetime.utcnow()
    payload = {
        "project_id": project_id,
        "created_at": now,
        "updated_at": now,
        **data,
    }
    storage.projects.create(payload)
    return payload


def list_projects(storage: StorageProtocol) -> list[dict[str, Any]]:
    """List all projects from storage."""
    if hasattr(storage.projects, "list_all"):
        return [dict(p) for p in storage.projects.list_all()]  # type: ignore[attr-defined]
    return []


def list_tasks_by_project(storage: StorageProtocol, project_id: str) -> list[dict[str, Any]]:
    """List tasks for a project."""
    return [dict(t) for t in storage.tasks.list_by_project(project_id)]
