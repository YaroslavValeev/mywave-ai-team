# Phase 8.2: Readiness — конфиг и runtime dependencies.
from __future__ import annotations

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

_ready: Tuple[bool, str] | None = None


def check_ready() -> Tuple[bool, str]:
    """Проверка готовности: конфиг и инициализация runtime deps. Возвращает (ready, reason)."""
    global _ready
    if _ready is not None:
        return _ready
    try:
        from . import config
        _ = config.host()
        _ = config.port()
    except Exception as e:
        _ready = (False, f"config: {e}")
        return _ready
    try:
        from .dependencies import get_molt_client
        get_molt_client()
    except Exception as e:
        logger.warning("readiness get_molt_client failed: %s", e)
        _ready = (False, f"runtime_deps: {e}")
        return _ready
    # Optional: Agents Control API (governance sync). Skip if AGENTS_CONTROL_ENABLED unset.
    try:
        from .agents_control import agents_health, is_enabled

        if is_enabled():
            ok, reason = agents_health()
            if not ok:
                _ready = (False, reason)
                return _ready
    except Exception as e:
        logger.warning("readiness agents_control failed: %s", e)
        _ready = (False, f"agents_control: {e}")
        return _ready
    _ready = (True, "")
    return _ready
