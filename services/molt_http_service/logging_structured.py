# Phase 8.4: Structured logging для boundary — единые ключи.
from __future__ import annotations

import json
import logging
from typing import Any

# Канонические ключи: request_id, trace_id, operation, endpoint, accepted, deduplicated, duration_ms, error_type, error_message, transport_mode
def log_boundary(log: logging.Logger, level: int, **kwargs: Any) -> None:
    payload = {k: v for k, v in kwargs.items() if v is not None and v != ""}
    msg = json.dumps(payload, ensure_ascii=False)
    log.log(level, msg)
