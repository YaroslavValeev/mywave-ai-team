# Конфиг Molt HTTP service (env).
from __future__ import annotations

import os
from typing import Optional


def host() -> str:
    return os.getenv("MOLT_HTTP_HOST", "0.0.0.0")


def port() -> int:
    try:
        return int(os.getenv("MOLT_HTTP_PORT", "8765"))
    except ValueError:
        return 8765
