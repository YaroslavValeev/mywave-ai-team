# Phase 8.2: Readiness — конфиг и runtime dependencies.
from __future__ import annotations

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Cache only successful ready=True. Failures must be re-checked (app may still be starting).
_ready_ok: bool = False


def check_ready() -> Tuple[bool, str]:
    """Проверка готовности: конфиг и инициализация runtime deps. Возвращает (ready, reason)."""
    global _ready_ok
    if _ready_ok:
        return True, ""

    try:
        from . import config

        _ = config.host()
        _ = config.port()
    except Exception as e:
        return False, f"config: {e}"

    try:
        from .dependencies import get_molt_client

        get_molt_client()
    except Exception as e:
        logger.warning("readiness get_molt_client failed: %s", e)
        return False, f"runtime_deps: {e}"

    # Optional: Agents Control API (governance sync). Skip if AGENTS_CONTROL_ENABLED unset.
    try:
        from .agents_control import agents_health, is_enabled

        if is_enabled():
            ok, reason = agents_health()
            if not ok:
                return False, reason
    except Exception as e:
        logger.warning("readiness agents_control failed: %s", e)
        return False, f"agents_control: {e}"

    _ready_ok = True
    return True, ""
