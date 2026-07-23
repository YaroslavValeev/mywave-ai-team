# Agents compatibility adapter (ADAPTER_STRATEGY). Stub implementation.
from __future__ import annotations

from typing import Any, Optional

from shared_core.protocols import StorageProtocol
from shared_core.crosswalk import CrosswalkStore
from shared_core import service_layer


SOURCE_SYSTEM = "agents"


def get_canonical_task_id(
    crosswalk: CrosswalkStore,
    legacy_task_id: str | int,
) -> Optional[str]:
    """По legacy task_id Agents возвращает canonical task_id."""
    return crosswalk.get_canonical(SOURCE_SYSTEM, "task", str(legacy_task_id))


def create_task_and_register(
    storage: StorageProtocol,
    crosswalk: CrosswalkStore,
    payload: dict[str, Any],
    legacy_task_id: Optional[str | int] = None,
) -> dict[str, Any]:
    """
    Создаёт Task через shared-core; регистрирует в crosswalk (agents, task, legacy_id, task, canonical_id).
    """
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


def create_approval_and_register(
    storage: StorageProtocol,
    crosswalk: CrosswalkStore,
    task_id: str,
    scope: str,
    run_id: Optional[str] = None,
    requested_by: Optional[str] = None,
    legacy_approval_id: Optional[str | int] = None,
    **extra: Any,
) -> dict[str, Any]:
    """
    Создаёт Approval через shared-core; опционально регистрирует в crosswalk.
    task_id — canonical task_id.
    """
    data = {"run_id": run_id, "requested_by": requested_by, **extra}
    approval_payload = service_layer.create_approval(storage, task_id, scope, data)
    canonical_id = approval_payload["approval_id"]
    if legacy_approval_id is not None:
        crosswalk.register(
            source_system=SOURCE_SYSTEM,
            legacy_entity_type="approval",
            legacy_id=str(legacy_approval_id),
            canonical_entity_type="approval",
            canonical_id=canonical_id,
        )
    return approval_payload
