# Phase 8.4: Минимальный runtime metrics для Molt boundary.
from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_requests_total = 0
_requests_by_operation: dict[str, int] = {}
_accepted_total = 0
_rejected_total = 0
_deduplicated_total = 0
_transport_error_total = 0
_business_rejection_total = 0
_health_checks_total = 0
_ready_checks_total = 0
_duration_sum_ms = 0.0
_duration_count = 0
_last_request_at: float | None = None


def record_boundary_request(
    operation: str,
    accepted: bool,
    deduplicated: bool,
    duration_ms: float,
    error_type: str | None = None,
) -> None:
    with _lock:
        global _requests_total, _requests_by_operation, _accepted_total, _rejected_total
        global _deduplicated_total, _transport_error_total, _business_rejection_total
        global _duration_sum_ms, _duration_count, _last_request_at
        _requests_total += 1
        _requests_by_operation[operation] = _requests_by_operation.get(operation, 0) + 1
        if accepted:
            _accepted_total += 1
        else:
            _rejected_total += 1
        if deduplicated:
            _deduplicated_total += 1
        if error_type == "transport_error":
            _transport_error_total += 1
        elif error_type == "business_rejection":
            _business_rejection_total += 1
        _duration_sum_ms += duration_ms
        _duration_count += 1
        _last_request_at = time.time()


def record_health_check() -> None:
    with _lock:
        global _health_checks_total
        _health_checks_total += 1


def record_ready_check() -> None:
    with _lock:
        global _ready_checks_total
        _ready_checks_total += 1


def get_metrics() -> dict[str, Any]:
    with _lock:
        avg_ms = (_duration_sum_ms / _duration_count) if _duration_count else None
        return {
            "requests_total": _requests_total,
            "requests_by_operation": dict(_requests_by_operation),
            "accepted_total": _accepted_total,
            "rejected_total": _rejected_total,
            "deduplicated_total": _deduplicated_total,
            "transport_error_total": _transport_error_total,
            "business_rejection_total": _business_rejection_total,
            "health_checks_total": _health_checks_total,
            "ready_checks_total": _ready_checks_total,
            "avg_duration_ms": round(avg_ms, 2) if avg_ms is not None else None,
            "last_request_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_last_request_at)) if _last_request_at else None,
        }
