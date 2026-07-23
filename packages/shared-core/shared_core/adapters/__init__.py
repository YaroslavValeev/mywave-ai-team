# Compatibility adapters (ADAPTER_STRATEGY). Stubs for Personal_Helper, Agents, Molt.
from shared_core.adapters.personal_helper_adapter import (
    legacy_task_to_canonical,
    canonical_task_to_legacy,
    create_task_via_core,
)
from shared_core.adapters.agents_adapter import (
    get_canonical_task_id,
    create_task_and_register,
    create_approval_and_register,
)
from shared_core.adapters.molt_adapter import (
    ensure_run_for_legacy_task,
    append_run_events,
    pause_for_approval,
    resume_after_approval,
)

__all__ = [
    "legacy_task_to_canonical",
    "canonical_task_to_legacy",
    "create_task_via_core",
    "get_canonical_task_id",
    "create_task_and_register",
    "create_approval_and_register",
    "ensure_run_for_legacy_task",
    "append_run_events",
    "pause_for_approval",
    "resume_after_approval",
]
