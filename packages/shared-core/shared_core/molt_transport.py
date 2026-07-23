# Phase 7.4/8.1: Transport-ready request/response контракты для Molt boundary.
# Сериализуемые модели для create_execution, emit_event, resolve_approval_runtime, handle_rework.
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


def request_to_dict(req: Any) -> dict[str, Any]:
    """Сериализация request в dict для JSON (HTTP)."""
    return asdict(req)


class MoltClientError(Exception):
    """Ошибка вызова Molt boundary. transport_error=True для сетевых/таймаут; иначе business/rejection."""
    def __init__(self, message: str, transport_error: bool = False):
        self.transport_error = transport_error
        super().__init__(message)


# --- Create execution ---

@dataclass(frozen=True)
class CreateExecutionRequest:
    canonical_task_id: str
    legacy_run_id: Optional[str] = None
    source_system: str = "agents"
    requested_by: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    request_id: Optional[str] = None  # Phase 8.3: boundary correlation / idempotency
    trace_id: Optional[str] = None


@dataclass
class CreateExecutionResponse:
    run_id: Optional[str] = None
    status: str = "created"
    accepted: bool = True
    error_message: Optional[str] = None
    request_id: Optional[str] = None  # Phase 8.3
    deduplicated: bool = False


# --- Emit execution event ---

@dataclass(frozen=True)
class EmitExecutionEventRequest:
    run_id: str
    event_type: str
    payload: Optional[dict[str, Any]] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass
class EmitExecutionEventResponse:
    accepted: bool = True
    error_message: Optional[str] = None
    request_id: Optional[str] = None
    deduplicated: bool = False


# --- Resolve approval runtime ---

@dataclass(frozen=True)
class ResolveApprovalRuntimeRequest:
    approval_id: str
    run_id: str
    approved: bool
    approved_by: Optional[str] = None
    comment: Optional[str] = None
    terminal_on_approve: bool = False
    request_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass
class ResolveApprovalRuntimeResponse:
    accepted: bool = True
    error_message: Optional[str] = None
    request_id: Optional[str] = None
    deduplicated: bool = False


# --- Handle rework ---

@dataclass(frozen=True)
class HandleReworkRequest:
    legacy_task_id: str | int
    canonical_task_id: str
    current_run_id: str
    approval_id: str
    approved_by: Optional[str] = None
    comment: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass
class HandleReworkResponse:
    new_run_id: Optional[str] = None
    status: str = "rework_done"
    accepted: bool = True
    error_message: Optional[str] = None
    request_id: Optional[str] = None
    deduplicated: bool = False


def dict_to_create_execution_response(d: dict) -> CreateExecutionResponse:
    """Парсинг ответа от сервиса."""
    return CreateExecutionResponse(
        run_id=d.get("run_id"),
        status=d.get("status", "created"),
        accepted=bool(d.get("accepted", True)),
        error_message=d.get("error_message"),
        request_id=d.get("request_id"),
        deduplicated=bool(d.get("deduplicated", False)),
    )


def dict_to_emit_execution_event_response(d: dict) -> EmitExecutionEventResponse:
    return EmitExecutionEventResponse(
        accepted=bool(d.get("accepted", True)),
        error_message=d.get("error_message"),
        request_id=d.get("request_id"),
        deduplicated=bool(d.get("deduplicated", False)),
    )


def dict_to_resolve_approval_runtime_response(d: dict) -> ResolveApprovalRuntimeResponse:
    return ResolveApprovalRuntimeResponse(
        accepted=bool(d.get("accepted", True)),
        error_message=d.get("error_message"),
        request_id=d.get("request_id"),
        deduplicated=bool(d.get("deduplicated", False)),
    )


def dict_to_handle_rework_response(d: dict) -> HandleReworkResponse:
    return HandleReworkResponse(
        new_run_id=d.get("new_run_id"),
        status=d.get("status", "rework_done"),
        accepted=bool(d.get("accepted", True)),
        error_message=d.get("error_message"),
        request_id=d.get("request_id"),
        deduplicated=bool(d.get("deduplicated", False)),
    )
