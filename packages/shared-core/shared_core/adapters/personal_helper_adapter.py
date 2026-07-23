# Personal_Helper compatibility adapter (ADAPTER_STRATEGY).
from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared_core.protocols import StorageProtocol
from shared_core.crosswalk import CrosswalkStore
from shared_core import service_layer


SOURCE_SYSTEM = "personal_helper"


def legacy_task_to_canonical(legacy_row: dict[str, Any]) -> dict[str, Any]:
    """Маппинг legacy task (SQLite/модель) в канонические поля Task."""
    return {
        "project_id": str(legacy_row.get("project_id", "")),
        "title": legacy_row.get("title", legacy_row.get("name", "")),
        "description": legacy_row.get("description", legacy_row.get("goal", "")),
        "priority": legacy_row.get("priority", "medium"),
        "origin_channel": legacy_row.get("origin_channel", "desktop"),
        "task_type": legacy_row.get("task_type"),
        "requested_by": legacy_row.get("requested_by"),
        "parent_task_id": legacy_row.get("parent_task_id"),
    }


def canonical_task_to_legacy(canonical_dict: dict[str, Any]) -> dict[str, Any]:
    """Маппинг канонического Task в формат, ожидаемый legacy UI."""
    return {
        "task_id": canonical_dict.get("task_id"),
        "project_id": canonical_dict.get("project_id"),
        "title": canonical_dict.get("title"),
        "description": canonical_dict.get("description"),
        "status": canonical_dict.get("status"),
        "priority": canonical_dict.get("priority"),
        "created_at": canonical_dict.get("created_at"),
        "updated_at": canonical_dict.get("updated_at"),
    }


def get_canonical_task_id(crosswalk: CrosswalkStore, legacy_task_id: str) -> Optional[str]:
    return crosswalk.get_canonical(
        SOURCE_SYSTEM,
        "task",
        str(legacy_task_id),
    )


def register_project_crosswalk(
    crosswalk: CrosswalkStore,
    legacy_project_id: str,
    canonical_project_id: str,
) -> None:
    crosswalk.register(
        source_system=SOURCE_SYSTEM,
        legacy_entity_type="project",
        legacy_id=str(legacy_project_id),
        canonical_entity_type="project",
        canonical_id=canonical_project_id,
    )


def create_task_via_core(
    storage: StorageProtocol,
    crosswalk: CrosswalkStore,
    legacy_project_id: str,
    payload: dict[str, Any],
    legacy_task_id: Optional[str] = None,
) -> dict[str, Any]:
    """Создаёт Task через shared-core; записывает crosswalk legacy_id -> canonical_id."""
    if "project_id" not in payload or not payload["project_id"]:
        canonical_pid = crosswalk.get_canonical(
            SOURCE_SYSTEM,
            "project",
            str(legacy_project_id),
        )
        payload["project_id"] = canonical_pid or legacy_project_id
    task_payload = service_layer.create_task(storage, payload)
    canonical_id = task_payload["task_id"]
    if legacy_task_id is not None:
        crosswalk.register(
            source_system=SOURCE_SYSTEM,
            legacy_entity_type="task",
            legacy_id=str(legacy_task_id),
            canonical_entity_type="task",
            canonical_id=canonical_id,
        )
    return task_payload


def list_legacy_tasks_from_core(
    storage: StorageProtocol,
    crosswalk: CrosswalkStore,
    canonical_project_id: str,
) -> List[dict[str, Any]]:
    """List tasks for UI from canonical store."""
    tasks = service_layer.list_tasks_by_project(storage, canonical_project_id)
    return [canonical_task_to_legacy(t) for t in tasks]


def sync_legacy_project_to_core(
    storage: StorageProtocol,
    crosswalk: CrosswalkStore,
    legacy_project: dict[str, Any],
) -> dict[str, Any]:
    """Ensure legacy project exists in canonical store."""
    legacy_id = str(legacy_project.get("id") or legacy_project.get("project_id"))
    existing = crosswalk.get_canonical(
        SOURCE_SYSTEM,
        "project",
        legacy_id,
    )
    if existing:
        proj = storage.projects.get(existing)
        if proj:
            return proj
    slug = (legacy_project.get("name") or f"project-{legacy_id}").lower().replace(" ", "-")[:48]
    proj = service_layer.create_project(storage, {
        "name": legacy_project.get("name", f"Project {legacy_id}"),
        "slug": slug,
        "status": legacy_project.get("status", "active"),
        "owner_id": legacy_project.get("owner_id", "owner"),
        "description": legacy_project.get("goal"),
    })
    register_project_crosswalk(crosswalk, legacy_id, proj["project_id"])
    return proj
