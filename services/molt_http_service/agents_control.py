"""Optional Agents Control API access from Molt (governance sync, not task SoT)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

_ENABLED = os.getenv("AGENTS_CONTROL_ENABLED", "").lower() in ("1", "true", "yes")


def is_enabled() -> bool:
    return _ENABLED


def _ensure_path() -> None:
    root = Path(__file__).resolve().parents[2]  # AI-Team
    candidates = [
        root / "packages" / "agents-http-client",
        root / "services" / "agents_live" / "packages" / "agents-http-client",
        Path(r"C:\ProjectMyWave\MyWave_AI_TEAM_Presets_v1_1\packages\agents-http-client"),
        Path(os.getenv("AGENTS_HTTP_CLIENT_PATH", "")),
    ]
    for p in candidates:
        if p and p.is_dir():
            s = str(p)
            if s not in sys.path:
                sys.path.insert(0, s)
            return


def get_client():
    _ensure_path()
    from agents_http_client import AgentsControlClient

    return AgentsControlClient.from_env()


def agents_health() -> tuple[bool, str]:
    """Return (ok, reason) for readiness probes."""
    if not is_enabled():
        return True, "agents_control_skipped"
    try:
        _ensure_path()
        data = get_client().health()
        if isinstance(data, dict) and data.get("status") == "ok":
            return True, "agents_ok"
        return False, f"agents_unexpected:{data}"
    except Exception as exc:
        return False, f"agents_error:{exc}"


def get_task(task_id: int | str) -> Optional[dict[str, Any]]:
    if not is_enabled():
        return None
    return get_client().get_task(task_id)
