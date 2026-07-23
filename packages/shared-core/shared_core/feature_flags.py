# Feature flags для canonical path (не расширять каркас без включённого флага).
from __future__ import annotations

import os
from typing import Optional


def canonical_path_enabled() -> bool:
    """Включён ли запись в shared-core параллельно legacy."""
    return os.getenv("CANONICAL_PATH_ENABLED", "").lower() in ("1", "true", "yes")


def canonical_storage_backend() -> str:
    """memory | sqlite."""
    return os.getenv("CANONICAL_STORAGE", "memory").lower().strip() or "memory"


def crosswalk_backend() -> str:
    """memory | sqlite."""
    return os.getenv("CROSSWALK_BACKEND", "memory").lower().strip() or "memory"


def canonical_sqlite_path() -> Optional[str]:
    """Путь к SQLite для canonical storage (при CANONICAL_STORAGE=sqlite)."""
    return os.getenv("CANONICAL_SQLITE_PATH", "").strip() or None


def crosswalk_sqlite_path() -> Optional[str]:
    """Путь к SQLite для crosswalk (при CROSSWALK_BACKEND=sqlite). Может совпадать с CANONICAL_SQLITE_PATH."""
    return os.getenv("CROSSWALK_SQLITE_PATH", os.getenv("CANONICAL_SQLITE_PATH", "")).strip() or None


def molt_run_owner() -> bool:
    """Phase 7: Molt владеет Run lifecycle. При true — Agents запрашивает execution у Molt."""
    return os.getenv("MOLT_RUN_OWNER", "").lower() in ("1", "true", "yes")


def should_agents_emit_execution_events() -> bool:
    """Phase 7.1: при true Agents может эмитить execution events напрямую; при false — только через Molt path."""
    return not molt_run_owner()


def should_agents_control_runtime_after_approval() -> bool:
    """Phase 7.2: при true Agents может выполнять terminal runtime transitions после approve/reject; при false — только Molt."""
    return not molt_run_owner()


def molt_transport_mode() -> str:
    """Phase 7.4/8.1: local | stub | http."""
    return (os.getenv("MOLT_TRANSPORT_MODE", "local") or "local").lower().strip()


def molt_http_base_url() -> Optional[str]:
    """Phase 8.1: базовый URL Molt HTTP service (без trailing slash)."""
    return (os.getenv("MOLT_HTTP_BASE_URL") or "").strip() or None


def molt_http_timeout_sec() -> float:
    """Phase 8.1: таймаут HTTP-запроса к Molt (секунды)."""
    try:
        return float(os.getenv("MOLT_HTTP_TIMEOUT_SEC", "30"))
    except ValueError:
        return 30.0


def molt_http_retries() -> int:
    """Phase 8.1: число повторов при transport failure (пока не используется)."""
    try:
        return max(0, int(os.getenv("MOLT_HTTP_RETRIES", "0")))
    except ValueError:
        return 0
