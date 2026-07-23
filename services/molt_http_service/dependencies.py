# Зависимости: единый LocalMoltClient из shared-core.
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_molt_client: Optional[object] = None


def get_molt_client():
    """Lazy init LocalMoltClient из shared_core.canonical_bridge."""
    global _molt_client
    if _molt_client is not None:
        return _molt_client
    try:
        from shared_core.canonical_bridge import get_local_molt_client
        _molt_client = get_local_molt_client()
        return _molt_client
    except Exception as e:
        logger.exception("get_local_molt_client failed: %s", e)
        raise
