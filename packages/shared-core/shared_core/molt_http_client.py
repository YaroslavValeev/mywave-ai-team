# Phase 8.1/8.3: HTTP-клиент к Molt service. Retry + request_id + observability.
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Tuple

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shared_core.molt_transport import (
    CreateExecutionRequest,
    CreateExecutionResponse,
    EmitExecutionEventRequest,
    EmitExecutionEventResponse,
    HandleReworkRequest,
    HandleReworkResponse,
    ResolveApprovalRuntimeRequest,
    ResolveApprovalRuntimeResponse,
    dict_to_create_execution_response,
    dict_to_emit_execution_event_response,
    dict_to_handle_rework_response,
    dict_to_resolve_approval_runtime_response,
    request_to_dict,
)

logger = logging.getLogger(__name__)


def _ensure_request_id(body: dict) -> str:
    """Добавляет request_id в body если нет; возвращает request_id."""
    rid = body.get("request_id") or ""
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    rid = str(uuid.uuid4())
    body["request_id"] = rid
    return rid


class HTTPMoltClient:
    """Клиент к Molt HTTP service. Phase 8.3: retry по idempotent contract, request_id, correlation в логах."""

    def __init__(self, base_url: str, timeout_sec: float = 30.0, max_retries: int = 0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_sec
        self._max_retries = max(0, max_retries)
        logger.info(
            "%s",
            json.dumps({"transport_mode": "http", "base_url": self._base, "timeout_sec": self._timeout, "max_retries": self._max_retries}),
        )

    def _post_attempt(self, path: str, body: dict) -> Tuple[dict, bool]:
        """Один запрос. Возвращает (response_dict, transport_error)."""
        url = f"{self._base}{path}"
        data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
                out = json.loads(raw) if raw else {}
                if not out.get("accepted", True):
                    logger.warning(
                        "%s",
                        json.dumps({
                            "error_type": "business_rejection",
                            "endpoint": path,
                            "request_id": body.get("request_id", ""),
                            "trace_id": body.get("trace_id") or None,
                            "error_message": (out.get("error_message") or "accepted=false")[:200],
                            "transport_mode": "http",
                        }),
                    )
                return out, False
        except HTTPError as e:
            err_raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
            logger.warning(
                "%s",
                json.dumps({
                    "error_type": "transport_error",
                    "endpoint": path,
                    "request_id": body.get("request_id", ""),
                    "trace_id": body.get("trace_id") or None,
                    "timeout_sec": self._timeout,
                    "http_code": e.code,
                    "transport_mode": "http",
                }),
            )
            try:
                err_body = json.loads(err_raw) if err_raw else {}
            except Exception:
                err_body = {}
            return {"accepted": False, "error_message": err_body.get("error_message") or f"HTTP {e.code}"}, True
        except URLError as e:
            logger.warning(
                "%s",
                json.dumps({
                    "error_type": "transport_error",
                    "endpoint": path,
                    "request_id": body.get("request_id", ""),
                    "timeout_sec": self._timeout,
                    "error_message": str(e.reason)[:200],
                    "transport_mode": "http",
                }),
            )
            return {"accepted": False, "error_message": str(e.reason)}, True
        except TimeoutError:
            logger.warning(
                "%s",
                json.dumps({
                    "error_type": "transport_error",
                    "endpoint": path,
                    "request_id": body.get("request_id", ""),
                    "timeout_sec": self._timeout,
                    "error_message": "timeout",
                    "transport_mode": "http",
                }),
            )
            return {"accepted": False, "error_message": "timeout"}, True
        except Exception as e:
            logger.warning(
                "%s",
                json.dumps({
                    "error_type": "transport_error",
                    "endpoint": path,
                    "request_id": body.get("request_id", ""),
                    "timeout_sec": self._timeout,
                    "error_message": str(e)[:200],
                    "transport_mode": "http",
                }),
            )
            return {"accepted": False, "error_message": str(e)}, True

    def _post(self, path: str, body: dict) -> dict:
        request_id = _ensure_request_id(body)
        trace_id = (body.get("trace_id") or "").strip() or None
        backoff_sec = 0.5
        last_out = None
        for attempt in range(self._max_retries + 1):
            out, transport_error = self._post_attempt(path, body)
            last_out = out
            if not transport_error:
                if attempt > 0:
                    logger.info("%s", json.dumps({"endpoint": path, "request_id": request_id, "trace_id": trace_id, "attempt": attempt + 1, "transport_mode": "http", "event": "success_after_retry"}))
                if out.get("deduplicated"):
                    logger.info("%s", json.dumps({"endpoint": path, "request_id": request_id, "trace_id": trace_id, "deduplicated": True, "transport_mode": "http"}))
                return out
            if attempt < self._max_retries:
                logger.info("%s", json.dumps({"endpoint": path, "request_id": request_id, "attempt": attempt + 1, "transport_mode": "http", "event": "retry", "next_in_sec": round(backoff_sec, 1)}))
                time.sleep(backoff_sec)
                backoff_sec = min(backoff_sec * 2, 10.0)
        return last_out or {"accepted": False, "error_message": "transport failure after retries"}

    def create_execution(self, request: CreateExecutionRequest) -> CreateExecutionResponse:
        body = request_to_dict(request)
        out = self._post("/executions", body)
        return dict_to_create_execution_response(out)

    def emit_execution_event(self, request: EmitExecutionEventRequest) -> EmitExecutionEventResponse:
        body = request_to_dict(request)
        out = self._post("/events", body)
        return dict_to_emit_execution_event_response(out)

    def resolve_approval_runtime(self, request: ResolveApprovalRuntimeRequest) -> ResolveApprovalRuntimeResponse:
        body = request_to_dict(request)
        out = self._post("/approvals/resolve-runtime", body)
        return dict_to_resolve_approval_runtime_response(out)

    def handle_rework(self, request: HandleReworkRequest) -> HandleReworkResponse:
        body = request_to_dict(request)
        out = self._post("/rework", body)
        return dict_to_handle_rework_response(out)
