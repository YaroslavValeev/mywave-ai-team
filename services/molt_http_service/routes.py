# Endpoints Molt HTTP service. Phase 8.2/8.3/8.4: ready, idempotency, observability.
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict
from typing import Any, Optional, Tuple

from fastapi import APIRouter, Depends, Request

from .dependencies import get_molt_client
from .idempotency import get_receipt, put_receipt
from .logging_structured import log_boundary
from .metrics import get_metrics, record_boundary_request, record_health_check, record_ready_check
from .readiness import check_ready
from .request_journal import append as journal_append

logger = logging.getLogger(__name__)
router = APIRouter()


def _record_and_log_boundary(
    request_id: str,
    operation: str,
    endpoint: str,
    accepted: bool,
    deduplicated: bool,
    duration_ms: float,
    trace_id: Optional[str] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    record_boundary_request(
        operation=operation,
        accepted=accepted,
        deduplicated=deduplicated,
        duration_ms=duration_ms,
        error_type=error_type,
    )
    journal_append(
        request_id=request_id,
        operation=operation,
        endpoint=endpoint,
        accepted=accepted,
        deduplicated=deduplicated,
        duration_ms=duration_ms,
        trace_id=trace_id,
        error_type=error_type,
        error_message=error_message,
    )
    log_boundary(
        logger,
        logging.INFO,
        request_id=request_id,
        trace_id=trace_id,
        operation=operation,
        endpoint=endpoint,
        accepted=accepted,
        deduplicated=deduplicated,
        duration_ms=round(duration_ms, 2),
        error_type=error_type,
        error_message=(error_message or "")[:200] if error_message else None,
    )


def _correlation(body: dict[str, Any], req: Request) -> Tuple[str, str]:
    """Phase 8.3: request_id и trace_id из body или headers; при отсутствии request_id — генерируем."""
    rid = (body.get("request_id") or req.headers.get("x-request-id") or "").strip()
    if not rid:
        rid = str(uuid.uuid4())
    trace_id = (body.get("trace_id") or req.headers.get("x-trace-id") or "").strip()
    return rid, trace_id


@router.get("/health")
def health() -> dict[str, str]:
    record_health_check()
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, Any]:
    """Phase 8.2: готовность к обслуживанию (конфиг + runtime deps)."""
    record_ready_check()
    ok, reason = check_ready()
    if ok:
        return {"status": "ready"}
    return {"status": "not_ready", "reason": reason}


@router.get("/metrics")
def metrics() -> dict[str, Any]:
    """Phase 8.4: операционная статистика boundary (JSON)."""
    return get_metrics()


@router.post("/executions")
def post_executions(body: dict[str, Any], req: Request, client=Depends(get_molt_client)) -> dict[str, Any]:
    from shared_core.molt_transport import CreateExecutionRequest
    rid, trace_id = _correlation(body, req)
    t0 = time.perf_counter()
    operation = "executions"
    endpoint = "/executions"
    existing = get_receipt(operation, rid)
    if existing is not None:
        duration_ms = (time.perf_counter() - t0) * 1000
        _record_and_log_boundary(rid, operation, endpoint, accepted=existing.get("accepted", True), deduplicated=True, duration_ms=duration_ms, trace_id=trace_id or None)
        return {**existing, "deduplicated": True}
    try:
        req_obj = CreateExecutionRequest(
            canonical_task_id=body["canonical_task_id"],
            legacy_run_id=body.get("legacy_run_id"),
            source_system=body.get("source_system", "agents"),
            requested_by=body.get("requested_by"),
            metadata=body.get("metadata"),
            request_id=rid,
            trace_id=trace_id or None,
        )
        resp = client.create_execution(req_obj)
        out = asdict(resp)
        out["request_id"] = rid
        out["deduplicated"] = False
        put_receipt(operation, rid, out, trace_id or None)
        duration_ms = (time.perf_counter() - t0) * 1000
        err_type = "business_rejection" if not resp.accepted else None
        _record_and_log_boundary(rid, operation, endpoint, accepted=resp.accepted, deduplicated=False, duration_ms=duration_ms, trace_id=trace_id or None, error_type=err_type, error_message=resp.error_message)
        return out
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        _record_and_log_boundary(rid, operation, endpoint, accepted=False, deduplicated=False, duration_ms=duration_ms, trace_id=trace_id or None, error_type="internal_error", error_message=str(e))
        logger.exception("operation=%s exception request_id=%s", operation, rid)
        return {"accepted": False, "error_message": str(e), "request_id": rid, "deduplicated": False}


@router.post("/events")
def post_events(body: dict[str, Any], req: Request, client=Depends(get_molt_client)) -> dict[str, Any]:
    from shared_core.molt_transport import EmitExecutionEventRequest
    rid, trace_id = _correlation(body, req)
    t0 = time.perf_counter()
    operation = "events"
    endpoint = "/events"
    existing = get_receipt(operation, rid)
    if existing is not None:
        duration_ms = (time.perf_counter() - t0) * 1000
        _record_and_log_boundary(rid, operation, endpoint, accepted=existing.get("accepted", True), deduplicated=True, duration_ms=duration_ms, trace_id=trace_id or None)
        return {**existing, "deduplicated": True}
    try:
        req_obj = EmitExecutionEventRequest(
            run_id=body["run_id"],
            event_type=body["event_type"],
            payload=body.get("payload"),
            request_id=rid,
            trace_id=trace_id or None,
        )
        resp = client.emit_execution_event(req_obj)
        out = asdict(resp)
        out["request_id"] = rid
        out["deduplicated"] = False
        put_receipt(operation, rid, out, trace_id or None)
        duration_ms = (time.perf_counter() - t0) * 1000
        err_type = "business_rejection" if not resp.accepted else None
        _record_and_log_boundary(rid, operation, endpoint, accepted=resp.accepted, deduplicated=False, duration_ms=duration_ms, trace_id=trace_id or None, error_type=err_type, error_message=resp.error_message)
        return out
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        _record_and_log_boundary(rid, operation, endpoint, accepted=False, deduplicated=False, duration_ms=duration_ms, trace_id=trace_id or None, error_type="internal_error", error_message=str(e))
        logger.exception("operation=%s exception request_id=%s", operation, rid)
        return {"accepted": False, "error_message": str(e), "request_id": rid, "deduplicated": False}


@router.post("/approvals/resolve-runtime")
def post_approvals_resolve_runtime(body: dict[str, Any], req: Request, client=Depends(get_molt_client)) -> dict[str, Any]:
    from shared_core.molt_transport import ResolveApprovalRuntimeRequest
    rid, trace_id = _correlation(body, req)
    t0 = time.perf_counter()
    operation = "approvals_resolve_runtime"
    endpoint = "/approvals/resolve-runtime"
    existing = get_receipt(operation, rid)
    if existing is not None:
        duration_ms = (time.perf_counter() - t0) * 1000
        _record_and_log_boundary(rid, operation, endpoint, accepted=existing.get("accepted", True), deduplicated=True, duration_ms=duration_ms, trace_id=trace_id or None)
        return {**existing, "deduplicated": True}
    try:
        req_obj = ResolveApprovalRuntimeRequest(
            approval_id=body["approval_id"],
            run_id=body["run_id"],
            approved=body["approved"],
            approved_by=body.get("approved_by"),
            comment=body.get("comment"),
            terminal_on_approve=body.get("terminal_on_approve", False),
            request_id=rid,
            trace_id=trace_id or None,
        )
        resp = client.resolve_approval_runtime(req_obj)
        out = asdict(resp)
        out["request_id"] = rid
        out["deduplicated"] = False
        put_receipt(operation, rid, out, trace_id or None)
        duration_ms = (time.perf_counter() - t0) * 1000
        err_type = "business_rejection" if not resp.accepted else None
        _record_and_log_boundary(rid, operation, endpoint, accepted=resp.accepted, deduplicated=False, duration_ms=duration_ms, trace_id=trace_id or None, error_type=err_type, error_message=resp.error_message)
        return out
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        _record_and_log_boundary(rid, operation, endpoint, accepted=False, deduplicated=False, duration_ms=duration_ms, trace_id=trace_id or None, error_type="internal_error", error_message=str(e))
        logger.exception("operation=%s exception request_id=%s", operation, rid)
        return {"accepted": False, "error_message": str(e), "request_id": rid, "deduplicated": False}


@router.post("/rework")
def post_rework(body: dict[str, Any], req: Request, client=Depends(get_molt_client)) -> dict[str, Any]:
    from shared_core.molt_transport import HandleReworkRequest
    rid, trace_id = _correlation(body, req)
    t0 = time.perf_counter()
    operation = "rework"
    endpoint = "/rework"
    existing = get_receipt(operation, rid)
    if existing is not None:
        duration_ms = (time.perf_counter() - t0) * 1000
        _record_and_log_boundary(rid, operation, endpoint, accepted=existing.get("accepted", True), deduplicated=True, duration_ms=duration_ms, trace_id=trace_id or None)
        return {**existing, "deduplicated": True}
    try:
        req_obj = HandleReworkRequest(
            legacy_task_id=body["legacy_task_id"],
            canonical_task_id=body["canonical_task_id"],
            current_run_id=body["current_run_id"],
            approval_id=body["approval_id"],
            approved_by=body.get("approved_by"),
            comment=body.get("comment"),
            request_id=rid,
            trace_id=trace_id or None,
        )
        resp = client.handle_rework(req_obj)
        out = asdict(resp)
        out["request_id"] = rid
        out["deduplicated"] = False
        put_receipt(operation, rid, out, trace_id or None)
        duration_ms = (time.perf_counter() - t0) * 1000
        err_type = "business_rejection" if not resp.accepted else None
        _record_and_log_boundary(rid, operation, endpoint, accepted=resp.accepted, deduplicated=False, duration_ms=duration_ms, trace_id=trace_id or None, error_type=err_type, error_message=resp.error_message)
        return out
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        _record_and_log_boundary(rid, operation, endpoint, accepted=False, deduplicated=False, duration_ms=duration_ms, trace_id=trace_id or None, error_type="internal_error", error_message=str(e))
        logger.exception("operation=%s exception request_id=%s", operation, rid)
        return {"accepted": False, "error_message": str(e), "request_id": rid, "deduplicated": False}
