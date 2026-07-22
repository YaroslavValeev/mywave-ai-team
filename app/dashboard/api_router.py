# app/dashboard/api_router.py — backward-compatible shim.
# Real implementation lives in app.dashboard.api package.

from app.dashboard.api import router, apply_owner_decision, apply_merge_confirmation  # noqa: F401
from app.dashboard.api.common import (  # noqa: F401
    ARTIFACTS_DIR,
    apply_merge_confirmation as _amc,
    apply_owner_decision as _aod,
    run_sync_orchestration,
    run_task_orchestration,
)

import app.dashboard.api.common as _common


def __getattr__(name: str):
    """Proxy attribute lookups to common so monkeypatching works on this module."""
    return getattr(_common, name)
