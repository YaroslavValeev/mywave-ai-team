# Мост для записи в canonical path из legacy (Agents/Molt). Вызывать только при CANONICAL_PATH_ENABLED.
from __future__ import annotations

import logging
from typing import Any, Optional

from shared_core import feature_flags
from shared_core import service_layer
from shared_core.adapters import agents_adapter
from shared_core.adapters import molt_adapter
from shared_core.protocols import StorageProtocol
from shared_core.crosswalk import CrosswalkStore, CrosswalkEntry
from shared_core.molt_client import LocalMoltClient, StubTransportMoltClient
from shared_core.molt_transport import (
    CreateExecutionRequest,
    EmitExecutionEventRequest,
    HandleReworkRequest,
    ResolveApprovalRuntimeRequest,
)

logger = logging.getLogger(__name__)

_storage: Optional[StorageProtocol] = None
_crosswalk: Optional[Any] = None  # CrosswalkStore | SQLiteCrosswalkStore
_runtime_state_store: Optional[Any] = None  # InMemoryRuntimeStateStore | SQLiteRuntimeStateStore
_default_project_id: Optional[str] = None
_molt_client: Optional[Any] = None  # MoltClientProtocol

SOURCE_SYSTEM_AGENTS = "agents"


def get_storage() -> Optional[StorageProtocol]:
    """Lazy init storage по CANONICAL_STORAGE."""
    global _storage
    if _storage is not None:
        return _storage
    if not feature_flags.canonical_path_enabled():
        return None
    backend = feature_flags.canonical_storage_backend()
    if backend == "sqlite":
        path = feature_flags.canonical_sqlite_path()
        if not path:
            logger.warning("CANONICAL_STORAGE=sqlite but CANONICAL_SQLITE_PATH not set")
            return None
        try:
            from shared_core.storage_impl import SQLiteStorage
            _storage = SQLiteStorage(path)
        except Exception as e:
            logger.warning("SQLiteStorage init failed: %s", e)
            return None
    else:
        try:
            from shared_core.storage_impl import InMemoryStorage
            _storage = InMemoryStorage()
        except Exception as e:
            logger.warning("InMemoryStorage init failed: %s", e)
            return None
    return _storage


def get_crosswalk() -> Optional[Any]:
    """Lazy init crosswalk по CROSSWALK_BACKEND."""
    global _crosswalk
    if _crosswalk is not None:
        return _crosswalk
    if not feature_flags.canonical_path_enabled():
        return None
    backend = feature_flags.crosswalk_backend()
    if backend == "sqlite":
        path = feature_flags.crosswalk_sqlite_path()
        if not path:
            path = feature_flags.canonical_sqlite_path()
        if not path:
            logger.warning("CROSSWALK_BACKEND=sqlite but no path set")
            return None
        try:
            from shared_core.crosswalk_sqlite import SQLiteCrosswalkStore
            _crosswalk = SQLiteCrosswalkStore(path)
        except Exception as e:
            logger.warning("SQLiteCrosswalkStore init failed: %s", e)
            return None
    else:
        _crosswalk = CrosswalkStore()
    return _crosswalk


def get_runtime_state_store() -> Optional[Any]:
    """Lazy init runtime state store. Uses same SQLite path as canonical storage when sqlite backend."""
    global _runtime_state_store
    if _runtime_state_store is not None:
        return _runtime_state_store
    if not feature_flags.canonical_path_enabled():
        return None
    backend = feature_flags.canonical_storage_backend()
    if backend == "sqlite":
        path = feature_flags.canonical_sqlite_path()
        if not path:
            logger.warning("Runtime state: CANONICAL_STORAGE=sqlite but CANONICAL_SQLITE_PATH not set")
            return None
        try:
            from shared_core.runtime_state import SQLiteRuntimeStateStore
            _runtime_state_store = SQLiteRuntimeStateStore(path)
        except Exception as e:
            logger.warning("SQLiteRuntimeStateStore init failed: %s", e)
            return None
    else:
        try:
            from shared_core.runtime_state import InMemoryRuntimeStateStore
            _runtime_state_store = InMemoryRuntimeStateStore()
        except Exception as e:
            logger.warning("InMemoryRuntimeStateStore init failed: %s", e)
            return None
    return _runtime_state_store


def upsert_runtime_state_agents(
    legacy_task_id: int | str,
    canonical_task_id: Optional[str] = None,
    run_id: Optional[str] = None,
    approval_id: Optional[str] = None,
    status: Optional[str] = None,
    last_event: Optional[str] = None,
    clear_approval: bool = False,
) -> None:
    """Записать/обновить runtime state для legacy task (Agents). clear_approval=True сбрасывает approval_id (rework)."""
    store = get_runtime_state_store()
    if not store:
        return
    updates = {}
    if canonical_task_id is not None:
        updates["canonical_task_id"] = canonical_task_id
    if run_id is not None:
        updates["run_id"] = run_id
    if clear_approval:
        updates["approval_id"] = None
    elif approval_id is not None:
        updates["approval_id"] = approval_id
    if status is not None:
        updates["status"] = status
    if last_event is not None:
        updates["last_event"] = last_event
    if updates:
        store.upsert(SOURCE_SYSTEM_AGENTS, str(legacy_task_id), **updates)


def get_runtime_state_agents(legacy_task_id: int | str) -> Optional[dict]:
    """Прочитать runtime state для legacy task (Agents)."""
    store = get_runtime_state_store()
    if not store:
        return None
    return store.get(SOURCE_SYSTEM_AGENTS, str(legacy_task_id))


def resolve_canonical_context_for_approval(legacy_task_id: int | str) -> Optional[dict]:
    """
    Fallback: восстановить canonical_task_id, run_id, approval_id через crosswalk + approvals.
    Используется когда runtime_state пуст (рестарт, старая запись).
    """
    canonical_task_id = get_canonical_task_id_agents(legacy_task_id)
    if not canonical_task_id:
        return None
    storage = get_storage()
    if not storage:
        return None
    approvals = storage.approvals.list_by_task(canonical_task_id)
    for a in approvals:
        rec = dict(a) if hasattr(a, "keys") else a
        if rec.get("status") == "requested" and rec.get("run_id"):
            return {
                "canonical_task_id": canonical_task_id,
                "run_id": rec["run_id"],
                "approval_id": rec.get("approval_id"),
                "status": "waiting_approval",
            }
    return None


def _ensure_default_project(storage: StorageProtocol) -> str:
    """Один проект по умолчанию для Telegram-first MVP."""
    global _default_project_id
    if _default_project_id:
        return _default_project_id
    proj = service_layer.create_project(storage, {
        "name": "Telegram MVP",
        "slug": "telegram_mvp",
        "status": "active",
        "owner_id": "telegram_owner",
    })
    _default_project_id = proj["project_id"]
    return _default_project_id


def create_task_and_register_agents(
    legacy_task_id: int | str,
    owner_text: str,
    origin_channel: str = "telegram",
) -> Optional[str]:
    """
    Создать canonical Task и записать в crosswalk (agents, task, legacy_id, task, canonical_id).
    Вызывать из Agents после repo.create_task(); при ошибке не падать, вернуть None.
    """
    if not feature_flags.canonical_path_enabled():
        return None
    storage = get_storage()
    crosswalk = get_crosswalk()
    if not storage or not crosswalk:
        return None
    try:
        project_id = _ensure_default_project(storage)
        payload = {
            "project_id": project_id,
            "title": (owner_text or "Task")[:500],
            "description": owner_text or "",
            "priority": "medium",
            "origin_channel": origin_channel,
        }
        task_payload = agents_adapter.create_task_and_register(
            storage, crosswalk, payload, legacy_task_id=legacy_task_id,
        )
        return task_payload.get("task_id")
    except Exception as e:
        logger.warning("Canonical create_task failed: %s", e)
        return None


def get_canonical_task_id_agents(legacy_task_id: int | str) -> Optional[str]:
    """По legacy task_id Agents вернуть canonical task_id."""
    crosswalk = get_crosswalk()
    if not crosswalk:
        return None
    return agents_adapter.get_canonical_task_id(crosswalk, legacy_task_id)


def create_run_for_task(canonical_task_id: str, legacy_run_id: Optional[str] = None) -> Optional[str]:
    """Создать Run для task (Molt). Возвращает canonical run_id."""
    storage = get_storage()
    crosswalk = get_crosswalk()
    if not storage or not canonical_task_id:
        return None
    try:
        run_payload = molt_adapter.ensure_run_for_legacy_task(
            storage, crosswalk or CrosswalkStore(), canonical_task_id, legacy_run_id,
        )
        return run_payload.get("run_id")
    except Exception as e:
        logger.warning("Canonical create_run failed: %s", e)
        return None


def get_local_molt_client() -> LocalMoltClient:
    """Phase 8.1: LocalMoltClient для использования HTTP-сервисом (тот же runtime, без transport)."""
    return LocalMoltClient(
        create_run_fn=create_run_for_task,
        append_event_fn=append_run_event,
        resolve_approval_fn=_resolve_approval_runtime_internal,
        handle_rework_fn=_handle_rework_internal,
    )


def _get_molt_client() -> Any:
    """Phase 7.4/8.1: единый клиент Molt boundary. local | stub | http."""
    global _molt_client
    if _molt_client is not None:
        return _molt_client
    mode = feature_flags.molt_transport_mode()
    if mode == "http":
        from shared_core.molt_http_client import HTTPMoltClient
        base_url = feature_flags.molt_http_base_url()
        timeout = feature_flags.molt_http_timeout_sec()
        if not base_url:
            logger.warning("MOLT_TRANSPORT_MODE=http but MOLT_HTTP_BASE_URL not set; falling back to local")
            mode = "local"
        else:
            retries = feature_flags.molt_http_retries()
            _molt_client = HTTPMoltClient(base_url=base_url, timeout_sec=timeout, max_retries=retries)
            return _molt_client
    local_client = LocalMoltClient(
        create_run_fn=create_run_for_task,
        append_event_fn=append_run_event,
        resolve_approval_fn=_resolve_approval_runtime_internal,
        handle_rework_fn=_handle_rework_internal,
    )
    _molt_client = StubTransportMoltClient(local_client) if mode == "stub" else local_client
    return _molt_client


def _resolve_approval_runtime_internal(
    approval_id: str,
    run_id: str,
    approved: bool,
    approved_by: Optional[str] = None,
    comment: Optional[str] = None,
    *,
    terminal_on_approve: bool = False,
) -> bool:
    """Внутренняя реализация resolve (storage + molt_adapter). Используется LocalMoltClient."""
    storage = get_storage()
    if not storage:
        return False
    try:
        molt_adapter.resume_after_approval(
            storage, approval_id, run_id, approved, approved_by, comment,
            terminal_on_approve=terminal_on_approve,
        )
        return True
    except Exception as e:
        logger.warning("_resolve_approval_runtime_internal failed: %s", e)
        return False


def _handle_rework_internal(
    legacy_task_id: int | str,
    canonical_task_id: str,
    current_run_id: str,
    approval_id: str,
    approved_by: Optional[str] = None,
    comment: Optional[str] = None,
) -> Optional[str]:
    """Внутренняя реализация rework (resolve + create_run + upsert state). Используется LocalMoltClient."""
    if not _resolve_approval_runtime_internal(
        approval_id, current_run_id, approved=False,
        approved_by=approved_by or "owner", comment=comment or "rework",
    ):
        return None
    new_run_id = create_run_for_task(canonical_task_id)
    if not new_run_id:
        return None
    upsert_runtime_state_agents(
        legacy_task_id,
        run_id=new_run_id,
        clear_approval=True,
        status="run_started",
        last_event="rework_new_run",
    )
    return new_run_id


def request_execution_from_molt(canonical_task_id: str, legacy_run_id: Optional[str] = None) -> Optional[str]:
    """
    Phase 7/7.4: запрос execution у Molt через client boundary. Возвращает run_id.
    """
    resp = _get_molt_client().create_execution(
        CreateExecutionRequest(canonical_task_id=canonical_task_id, legacy_run_id=legacy_run_id),
    )
    return resp.run_id if resp.accepted and resp.run_id else None


def append_run_event(run_id: str, event_type: str, payload: Optional[dict] = None) -> bool:
    """Записать ExecutionEvent (legacy/direct path)."""
    storage = get_storage()
    if not storage:
        return False
    try:
        service_layer.append_event(storage, run_id, event_type, payload)
        return True
    except Exception as e:
        logger.warning("Canonical append_event failed: %s", e)
        return False


def emit_execution_event_via_molt(run_id: str, event_type: str, payload: Optional[dict] = None) -> bool:
    """
    Phase 7.1/7.4: Molt-owned event emission через client boundary.
    """
    resp = _get_molt_client().emit_execution_event(
        EmitExecutionEventRequest(run_id=run_id, event_type=event_type, payload=payload),
    )
    return resp.accepted


def request_approval_and_pause_run(
    canonical_task_id: str,
    run_id: str,
    scope: str,
    requested_by: Optional[str] = None,
) -> Optional[str]:
    """Создать Approval (requested), перевести Run в waiting_approval. Возвращает approval_id."""
    storage = get_storage()
    if not storage:
        return None
    try:
        approval = molt_adapter.pause_for_approval(
            storage, canonical_task_id, run_id, scope, requested_by,
        )
        return approval.get("approval_id")
    except Exception as e:
        logger.warning("Canonical pause_for_approval failed: %s", e)
        return None


def resolve_approval(approval_id: str, run_id: str, approved: bool, approved_by: Optional[str] = None, comment: Optional[str] = None) -> bool:
    """Обновить Approval и Run после решения owner (legacy path: resumed/cancelled, без terminal success)."""
    storage = get_storage()
    if not storage:
        return False
    try:
        molt_adapter.resume_after_approval(storage, approval_id, run_id, approved, approved_by, comment, terminal_on_approve=False)
        return True
    except Exception as e:
        logger.warning("Canonical resolve_approval failed: %s", e)
        return False


def resolve_approval_and_runtime_via_molt(
    approval_id: str,
    run_id: str,
    approved: bool,
    approved_by: Optional[str] = None,
    comment: Optional[str] = None,
    *,
    terminal_on_approve: bool = False,
) -> bool:
    """
    Phase 7.2/7.4: Molt-owned approval resolution и runtime control через client boundary.
    """
    resp = _get_molt_client().resolve_approval_runtime(
        ResolveApprovalRuntimeRequest(
            approval_id=approval_id,
            run_id=run_id,
            approved=approved,
            approved_by=approved_by,
            comment=comment,
            terminal_on_approve=terminal_on_approve,
        ),
    )
    return resp.accepted


def handle_rework_via_molt(
    legacy_task_id: int | str,
    canonical_task_id: str,
    current_run_id: str,
    approval_id: str,
    approved_by: Optional[str] = None,
    comment: Optional[str] = None,
) -> Optional[str]:
    """
    Phase 7.3/7.4: Molt-owned rework через client boundary. Возвращает new_run_id.
    """
    resp = _get_molt_client().handle_rework(
        HandleReworkRequest(
            legacy_task_id=legacy_task_id,
            canonical_task_id=canonical_task_id,
            current_run_id=current_run_id,
            approval_id=approval_id,
            approved_by=approved_by,
            comment=comment,
        ),
    )
    return resp.new_run_id if resp.accepted and resp.new_run_id else None


def create_artifact_for_task(task_id: str, artifact_type: str, storage_uri: str, run_id: Optional[str] = None, title: Optional[str] = None) -> Optional[str]:
    """Создать Artifact, привязать к task (и опционально run). Возвращает artifact_id."""
    storage = get_storage()
    if not storage:
        return None
    try:
        data = {}
        if run_id:
            data["run_id"] = run_id
        if title:
            data["title"] = title
        art = service_layer.create_artifact(storage, task_id, artifact_type, storage_uri, data)
        return art.get("artifact_id")
    except Exception as e:
        logger.warning("Canonical create_artifact failed: %s", e)
        return None
