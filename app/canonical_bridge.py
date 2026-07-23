# Тонкая прослойка: вызов shared-core при CANONICAL_PATH_ENABLED.
# Требует PYTHONPATH с packages/shared-core (или установленный пакет shared-core).
from __future__ import annotations

from typing import Optional

try:
    from shared_core.canonical_bridge import (
        create_task_and_register_agents,
        get_canonical_task_id_agents,
        create_run_for_task,
        request_execution_from_molt,
        append_run_event,
        emit_execution_event_via_molt,
        request_approval_and_pause_run,
        resolve_approval,
        resolve_approval_and_runtime_via_molt,
        handle_rework_via_molt,
        create_artifact_for_task,
        upsert_runtime_state_agents,
        get_runtime_state_agents,
        resolve_canonical_context_for_approval,
    )
    from shared_core.feature_flags import (
        canonical_path_enabled,
        molt_run_owner,
        should_agents_emit_execution_events,
        should_agents_control_runtime_after_approval,
    )
    _available = True
except ImportError:
    _available = False
    create_task_and_register_agents = None
    get_canonical_task_id_agents = None
    create_run_for_task = None
    request_execution_from_molt = None
    molt_run_owner = lambda: False
    should_agents_emit_execution_events = lambda: True
    append_run_event = None
    emit_execution_event_via_molt = None
    request_approval_and_pause_run = None
    resolve_approval = None
    resolve_approval_and_runtime_via_molt = None
    handle_rework_via_molt = None
    should_agents_control_runtime_after_approval = lambda: True
    create_artifact_for_task = None
    upsert_runtime_state_agents = None
    get_runtime_state_agents = None
    resolve_canonical_context_for_approval = None
    canonical_path_enabled = lambda: False


def is_canonical_path_available() -> bool:
    return _available and canonical_path_enabled()


def write_canonical_task_if_enabled(
    legacy_task_id: int | str,
    owner_text: str,
    origin_channel: str = "telegram",
) -> Optional[str]:
    """После repo.create_task() вызвать для записи в shared-core и crosswalk. Не ломает legacy при ошибке."""
    if not _available or not canonical_path_enabled():
        return None
    try:
        return create_task_and_register_agents(
            legacy_task_id=legacy_task_id,
            owner_text=owner_text,
            origin_channel=origin_channel,
        )
    except Exception:
        return None


def get_canonical_task_id(legacy_task_id: int | str) -> Optional[str]:
    """По legacy task_id вернуть canonical task_id из crosswalk."""
    if not _available:
        return None
    try:
        return get_canonical_task_id_agents(legacy_task_id)
    except Exception:
        return None


def write_run_if_enabled(canonical_task_id: str, legacy_run_id: Optional[str] = None) -> Optional[str]:
    """В точке старта выполнения: создать Run. При MOLT_RUN_OWNER — запрос execution у Molt."""
    if not _available or not canonical_path_enabled():
        return None
    try:
        if molt_run_owner() and request_execution_from_molt:
            return request_execution_from_molt(canonical_task_id, legacy_run_id)
        return create_run_for_task(canonical_task_id, legacy_run_id)
    except Exception:
        return None


def write_event_if_enabled(run_id: str, event_type: str, payload: Optional[dict] = None) -> bool:
    """Записать ExecutionEvent. При MOLT_RUN_OWNER=true — через Molt path; иначе legacy (Agents path). Без дублей."""
    if not _available or not canonical_path_enabled():
        return False
    if should_agents_emit_execution_events() and append_run_event:
        return append_run_event(run_id, event_type, payload)
    if emit_execution_event_via_molt:
        return emit_execution_event_via_molt(run_id, event_type, payload)
    return False


def write_approval_request_if_enabled(
    canonical_task_id: str,
    run_id: str,
    scope: str,
    requested_by: Optional[str] = None,
) -> Optional[str]:
    """Перед ожиданием approve: создать Approval, перевести Run в waiting_approval."""
    if not _available or not canonical_path_enabled():
        return None
    try:
        return request_approval_and_pause_run(canonical_task_id, run_id, scope, requested_by)
    except Exception:
        return None


def handle_rework_via_molt_if_enabled(
    legacy_task_id: int | str,
    canonical_task_id: str,
    current_run_id: str,
    approval_id: str,
    approved_by: Optional[str] = None,
    comment: Optional[str] = None,
) -> Optional[str]:
    """Phase 7.3: при MOLT_RUN_OWNER — единая Molt rework: закрыть run, создать новый, обновить state. Возвращает new_run_id или None."""
    if not _available or not canonical_path_enabled() or not molt_run_owner() or not handle_rework_via_molt:
        return None
    try:
        return handle_rework_via_molt(
            legacy_task_id, canonical_task_id, current_run_id, approval_id,
            approved_by=approved_by, comment=comment,
        )
    except Exception:
        return None


def write_approval_resolution_if_enabled(
    approval_id: str,
    run_id: str,
    approved: bool,
    approved_by: Optional[str] = None,
    comment: Optional[str] = None,
    *,
    terminal_on_approve: bool = False,
) -> bool:
    """После нажатия Approve/Rework: обновить Approval и Run. При MOLT_RUN_OWNER — через Molt path (terminal_on_approve при approve-as-done)."""
    if not _available or not canonical_path_enabled():
        return False
    if molt_run_owner() and resolve_approval_and_runtime_via_molt:
        return resolve_approval_and_runtime_via_molt(
            approval_id, run_id, approved, approved_by, comment,
            terminal_on_approve=terminal_on_approve,
        )
    return resolve_approval(approval_id, run_id, approved, approved_by, comment)


def write_artifact_if_enabled(
    task_id: str,
    artifact_type: str,
    storage_uri: str,
    run_id: Optional[str] = None,
    title: Optional[str] = None,
) -> Optional[str]:
    """На завершении: создать Artifact в shared-core."""
    if not _available or not canonical_path_enabled():
        return None
    try:
        return create_artifact_for_task(task_id, artifact_type, storage_uri, run_id, title)
    except Exception:
        return None


# Fallback in-memory кэш только при отключённом canonical path или недоступном shared-core.
_canonical_state: dict[int | str, dict] = {}


def set_canonical_state(
    legacy_task_id: int | str,
    canonical_task_id: Optional[str] = None,
    run_id: Optional[str] = None,
    approval_id: Optional[str] = None,
    status: Optional[str] = None,
    last_event: Optional[str] = None,
    clear_approval: bool = False,
) -> None:
    """Записать runtime state. При CANONICAL_PATH_ENABLED пишет в persisted store. clear_approval=True для rework."""
    if _available and canonical_path_enabled() and upsert_runtime_state_agents:
        try:
            upsert_runtime_state_agents(
                legacy_task_id,
                canonical_task_id=canonical_task_id,
                run_id=run_id,
                approval_id=approval_id,
                status=status,
                last_event=last_event,
                clear_approval=clear_approval,
            )
        except Exception:
            pass
    # Fallback in-memory для обратной совместимости при отключённом canonical path
    key = legacy_task_id
    if key not in _canonical_state:
        _canonical_state[key] = {}
    if canonical_task_id is not None:
        _canonical_state[key]["canonical_task_id"] = canonical_task_id
    if run_id is not None:
        _canonical_state[key]["run_id"] = run_id
    if clear_approval:
        _canonical_state[key].pop("approval_id", None)
    elif approval_id is not None:
        _canonical_state[key]["approval_id"] = approval_id
    if status is not None:
        _canonical_state[key]["status"] = status
    if last_event is not None:
        _canonical_state[key]["last_event"] = last_event


def get_canonical_state(legacy_task_id: int | str) -> dict:
    """
    Прочитать runtime state. Сначала persisted store, затем fallback через crosswalk+approvals,
    в конце — in-memory кэш (при отключённом canonical path).
    """
    if _available and canonical_path_enabled():
        try:
            state = get_runtime_state_agents(legacy_task_id)
            if state and (state.get("run_id") or state.get("approval_id") or state.get("canonical_task_id")):
                return state
            # Fallback: восстановить через crosswalk + approvals
            if resolve_canonical_context_for_approval:
                resolved = resolve_canonical_context_for_approval(legacy_task_id)
                if resolved:
                    upsert_runtime_state_agents(legacy_task_id, **resolved)
                    return resolved
        except Exception:
            pass
    return _canonical_state.get(legacy_task_id, {})
