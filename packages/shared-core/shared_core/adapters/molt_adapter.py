# Molt compatibility adapter (ADAPTER_STRATEGY). Stub implementation.
from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared_core.protocols import StorageProtocol
from shared_core.crosswalk import CrosswalkStore
from shared_core import service_layer


SOURCE_SYSTEM = "molt"
ORCHESTRATOR = "molt"


def ensure_run_for_legacy_task(
    storage: StorageProtocol,
    crosswalk: CrosswalkStore,
    task_id: str,
    legacy_run_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Создаёт Run для task_id через shared-core; опционально регистрирует legacy_run_id в crosswalk.
    task_id — канонический task_id.
    """
    run_payload = service_layer.create_run(storage, task_id, ORCHESTRATOR)
    canonical_run_id = run_payload["run_id"]
    if legacy_run_id is not None:
        crosswalk.register(
            source_system=SOURCE_SYSTEM,
            legacy_entity_type="run",
            legacy_id=str(legacy_run_id),
            canonical_entity_type="run",
            canonical_id=canonical_run_id,
        )
    return run_payload


def append_run_events(
    storage: StorageProtocol,
    run_id: str,
    events: List[Dict[str, Any]],
) -> List[dict]:
    """
    Пишет список событий в EventRepository. Каждый элемент: {"event_type": str, **payload}.
    """
    result = []
    for ev in events:
        event_type = ev.get("event_type", "run_event")
        payload = service_layer.append_event(storage, run_id, event_type, ev)
        result.append(payload)
    return result


def pause_for_approval(
    storage: StorageProtocol,
    task_id: str,
    run_id: str,
    scope: str,
    requested_by: Optional[str] = None,
) -> dict[str, Any]:
    """
    Создаёт Approval (requested); вызывающая сторона должна перевести Run в waiting_approval.
    """
    approval = service_layer.create_approval(
        storage, task_id, scope,
        data={"run_id": run_id, "requested_by": requested_by},
    )
    storage.runs.update(run_id, {"status": "waiting_approval"})
    return approval


def resume_after_approval(
    storage: StorageProtocol,
    approval_id: str,
    run_id: str,
    approved: bool,
    approved_by: Optional[str] = None,
    comment: Optional[str] = None,
    *,
    terminal_on_approve: bool = False,
) -> None:
    """
    Обновляет Approval (approved/rejected); переводит Run в resumed/succeeded или cancelled.
    terminal_on_approve: при True и approved — run переводится в succeeded и пишется run_succeeded (Phase 7.2).
    """
    status = "approved" if approved else "rejected"
    from datetime import datetime
    storage.approvals.update(approval_id, {
        "status": status,
        "approved_by": approved_by,
        "approved_at": datetime.utcnow(),
        "comment": comment,
    })
    if approved:
        if terminal_on_approve:
            storage.runs.update(run_id, {"status": "succeeded"})
            service_layer.append_event(storage, run_id, "run_succeeded", {"approval_id": approval_id, "decision": "approve"})
        else:
            storage.runs.update(run_id, {"status": "resumed"})
            service_layer.append_event(storage, run_id, "run_resumed", {"approval_id": approval_id})
    else:
        storage.runs.update(run_id, {"status": "cancelled", "error_summary": comment or "Rejected by owner"})
        service_layer.append_event(storage, run_id, "run_cancelled", {"approval_id": approval_id})
