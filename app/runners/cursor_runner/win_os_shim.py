# Windows Python lacks Unix-only os.get_blocking/set_blocking; cursor-sdk may call them.
"""Idempotent shim so Cursor SDK imports work on Windows."""
from __future__ import annotations

import os
from typing import Any


def ensure_windows_os_blocking_shim() -> bool:
    """Install no-op get_blocking/set_blocking if missing. Returns True if installed."""
    if hasattr(os, "get_blocking") and hasattr(os, "set_blocking"):
        return False

    def _get_blocking(fd: int) -> bool:  # noqa: ARG001
        return True

    def _set_blocking(fd: int, blocking: bool) -> None:  # noqa: ARG001
        return None

    os.get_blocking = _get_blocking  # type: ignore[attr-defined]
    os.set_blocking = _set_blocking  # type: ignore[attr-defined]
    return True


def shim_installed() -> bool:
    """True when both attrs exist (native or shimmed)."""
    return hasattr(os, "get_blocking") and hasattr(os, "set_blocking")


def call_get_blocking(fd: int = 0) -> Any:
    """Helper for tests: invoke get_blocking after ensure."""
    ensure_windows_os_blocking_shim()
    return os.get_blocking(fd)  # type: ignore[attr-defined]
