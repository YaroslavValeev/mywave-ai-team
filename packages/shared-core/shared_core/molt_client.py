# Phase 7.4: Molt client interface и реализации (local / stub transport).
from __future__ import annotations

import logging
from typing import Callable, Optional, Protocol

from shared_core.molt_transport import (
    CreateExecutionRequest,
    CreateExecutionResponse,
    EmitExecutionEventRequest,
    EmitExecutionEventResponse,
    HandleReworkRequest,
    HandleReworkResponse,
    ResolveApprovalRuntimeRequest,
    ResolveApprovalRuntimeResponse,
)

logger = logging.getLogger(__name__)


class MoltClientProtocol(Protocol):
    """Transport-ready клиентский интерфейс Molt boundary."""

    def create_execution(self, request: CreateExecutionRequest) -> CreateExecutionResponse:
        ...

    def emit_execution_event(self, request: EmitExecutionEventRequest) -> EmitExecutionEventResponse:
        ...

    def resolve_approval_runtime(self, request: ResolveApprovalRuntimeRequest) -> ResolveApprovalRuntimeResponse:
        ...

    def handle_rework(self, request: HandleReworkRequest) -> HandleReworkResponse:
        ...


class LocalMoltClient:
    """In-process реализация: вызывает переданные реализации (storage/adapter)."""

    def __init__(
        self,
        create_run_fn: Callable[[str, Optional[str]], Optional[str]],
        append_event_fn: Callable[[str, str, Optional[dict]], bool],
        resolve_approval_fn: Callable[..., bool],
        handle_rework_fn: Callable[..., Optional[str]],
    ):
        self._create_run = create_run_fn
        self._append_event = append_event_fn
        self._resolve_approval = resolve_approval_fn
        self._handle_rework = handle_rework_fn

    def create_execution(self, request: CreateExecutionRequest) -> CreateExecutionResponse:
        try:
            run_id = self._create_run(request.canonical_task_id, request.legacy_run_id)
            if run_id:
                return CreateExecutionResponse(run_id=run_id, status="created", accepted=True)
            return CreateExecutionResponse(accepted=False, error_message="create_run returned None")
        except Exception as e:
            logger.warning("LocalMoltClient create_execution failed: %s", e)
            return CreateExecutionResponse(accepted=False, error_message=str(e))

    def emit_execution_event(self, request: EmitExecutionEventRequest) -> EmitExecutionEventResponse:
        try:
            ok = self._append_event(request.run_id, request.event_type, request.payload)
            return EmitExecutionEventResponse(accepted=ok)
        except Exception as e:
            logger.warning("LocalMoltClient emit_execution_event failed: %s", e)
            return EmitExecutionEventResponse(accepted=False, error_message=str(e))

    def resolve_approval_runtime(self, request: ResolveApprovalRuntimeRequest) -> ResolveApprovalRuntimeResponse:
        try:
            ok = self._resolve_approval(
                request.approval_id,
                request.run_id,
                request.approved,
                request.approved_by,
                request.comment,
                terminal_on_approve=request.terminal_on_approve,
            )
            return ResolveApprovalRuntimeResponse(accepted=ok)
        except Exception as e:
            logger.warning("LocalMoltClient resolve_approval_runtime failed: %s", e)
            return ResolveApprovalRuntimeResponse(accepted=False, error_message=str(e))

    def handle_rework(self, request: HandleReworkRequest) -> HandleReworkResponse:
        try:
            new_run_id = self._handle_rework(
                request.legacy_task_id,
                request.canonical_task_id,
                request.current_run_id,
                request.approval_id,
                request.approved_by,
                request.comment,
            )
            if new_run_id:
                return HandleReworkResponse(new_run_id=new_run_id, status="rework_done", accepted=True)
            return HandleReworkResponse(accepted=False, error_message="handle_rework returned None")
        except Exception as e:
            logger.warning("LocalMoltClient handle_rework failed: %s", e)
            return HandleReworkResponse(accepted=False, error_message=str(e))


class StubTransportMoltClient:
    """
    Transport-shaped клиент: принимает request/response, делегирует в local реализацию.
    Имитирует границу transport (сериализация payload возможна здесь); реальный HTTP/IPC не делаем.
    """

    def __init__(self, local_client: LocalMoltClient):
        self._local = local_client

    def create_execution(self, request: CreateExecutionRequest) -> CreateExecutionResponse:
        return self._local.create_execution(request)

    def emit_execution_event(self, request: EmitExecutionEventRequest) -> EmitExecutionEventResponse:
        return self._local.emit_execution_event(request)

    def resolve_approval_runtime(self, request: ResolveApprovalRuntimeRequest) -> ResolveApprovalRuntimeResponse:
        return self._local.resolve_approval_runtime(request)

    def handle_rework(self, request: HandleReworkRequest) -> HandleReworkResponse:
        return self._local.handle_rework(request)
