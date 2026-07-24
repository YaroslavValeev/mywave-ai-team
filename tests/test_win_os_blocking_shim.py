"""Unit tests for Windows os.get_blocking shim (no live CURSOR_API_KEY)."""
from __future__ import annotations

import os

from app.runners.cursor_runner.win_os_shim import (
    call_get_blocking,
    ensure_windows_os_blocking_shim,
    shim_installed,
)


def test_ensure_shim_idempotent() -> None:
    first = ensure_windows_os_blocking_shim()
    second = ensure_windows_os_blocking_shim()
    assert shim_installed()
    # Second call must not reinstall when attrs already exist
    assert second is False
    # On Windows without native attrs, first may be True; on Unix, first is False
    assert isinstance(first, bool)


def test_get_blocking_callable() -> None:
    ensure_windows_os_blocking_shim()
    assert callable(os.get_blocking)  # type: ignore[attr-defined]
    assert callable(os.set_blocking)  # type: ignore[attr-defined]
    value = call_get_blocking(0)
    assert isinstance(value, bool)
