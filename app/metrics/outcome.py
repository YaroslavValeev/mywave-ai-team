"""Deterministic outcome metrics derived from persisted mission data.

The module deliberately has no database or application-service dependencies.  It
accepts SQLAlchemy-like objects as well as mappings, which keeps calculations
reusable in API, reporting, and offline analytics code.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


_IGNORED_EVENT_TYPES = {
    "api_request",
    "chat_message",
    "owner_chat_message",
    "task_created",
}

_OWNER_ACTION_EVENT_TYPES = {
    "exploration_option_selected",
    "workflow_cancelled_by_owner",
    "workflow_paused_by_owner",
    "workflow_resumed_by_owner",
}

_ACTION_EVENT_MARKERS = (
    "approve",
    "cancel",
    "clarif",
    "complete",
    "done",
    "execute",
    "execution",
    "merge",
    "pipeline",
    "prepare",
    "rework",
    "roundtable",
    "select",
    "start",
    "stop",
    "triage",
    "validat",
)

_OWNER_ACTORS = {"owner", "владелец", "human", "manual"}
_AUTONOMOUS_ACTORS = {"agent", "ai", "autonomous", "automation", "system"}


def _read(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _first_number(*values: Any) -> float | None:
    for value in values:
        result = _number(value)
        if result is not None:
            return result
    return None


def _event_type(event: Any) -> str:
    return str(_read(event, "event_type", "") or "").strip().lower()


def _event_payload(event: Any) -> Mapping[str, Any]:
    return _mapping(_read(event, "payload_json", _read(event, "payload", {})))


def _event_actor(event: Any) -> str:
    payload = _event_payload(event)
    return str(payload.get("actor") or payload.get("performed_by") or payload.get("source") or "").strip().lower()


def _is_owner_action(event: Any) -> bool:
    kind = _event_type(event)
    actor = _event_actor(event)
    return kind.startswith("owner_") or kind in _OWNER_ACTION_EVENT_TYPES or actor in _OWNER_ACTORS


def _is_action_event(event: Any) -> bool:
    kind = _event_type(event)
    if not kind or kind in _IGNORED_EVENT_TYPES:
        return False
    return _is_owner_action(event) or any(marker in kind for marker in _ACTION_EVENT_MARKERS)


def _is_autonomous_action(event: Any) -> bool:
    if not _is_action_event(event) or _is_owner_action(event):
        return False
    actor = _event_actor(event)
    return actor not in _OWNER_ACTORS


def _duration_minutes(payload: Mapping[str, Any]) -> float:
    nested = _mapping(payload.get("metrics"))
    value = _first_number(
        payload.get("owner_minutes"),
        payload.get("duration_minutes"),
        payload.get("active_minutes"),
        nested.get("owner_minutes"),
        nested.get("duration_minutes"),
    )
    return value or 0.0


def _manual_estimate_minutes(payload: Mapping[str, Any]) -> float:
    nested = _mapping(payload.get("metrics"))
    value = _first_number(
        payload.get("estimated_manual_minutes"),
        payload.get("manual_estimate_minutes"),
        nested.get("estimated_manual_minutes"),
        nested.get("manual_estimate_minutes"),
    )
    return value or 0.0


def _structured_actions(business_action: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("actions", "execution_actions"):
        value = business_action.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]

    scenario = _mapping(business_action.get("execution_from_scenario"))
    agent_tasks = scenario.get("agent_tasks")
    if isinstance(agent_tasks, list):
        return [item for item in agent_tasks if isinstance(item, Mapping)]

    instance = business_action.get("action_instance")
    if isinstance(instance, Mapping) and str(instance.get("status") or "pending").lower() != "pending":
        return [instance]
    return []


def _structured_action_is_autonomous(action: Mapping[str, Any]) -> bool:
    explicit = action.get("autonomous")
    if isinstance(explicit, bool):
        return explicit
    actor = str(action.get("actor") or action.get("performed_by") or action.get("source") or "").strip().lower()
    if actor in _OWNER_ACTORS:
        return False
    if actor in _AUTONOMOUS_ACTORS:
        return True
    return bool(action.get("agent") or action.get("agent_id") or action.get("role"))


def _business_outcome(task: Any, business_action: Mapping[str, Any]) -> str:
    task_outcome = _read(task, "business_outcome", "")
    if isinstance(task_outcome, str) and task_outcome.strip():
        return task_outcome.strip()

    metrics = _mapping(business_action.get("outcome_metrics"))
    action = _mapping(business_action.get("action_instance"))
    for value in (
        metrics.get("business_outcome"),
        business_action.get("business_outcome"),
        business_action.get("outcome"),
        action.get("result_summary"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def calculate_outcome_metrics(task: Any, audit_events: Iterable[Any] | None = None) -> dict[str, Any]:
    """Calculate mission KPI without mutating inputs or accessing persistence.

    Explicit values in ``business_action_json.outcome_metrics`` are authoritative.
    Missing counters are inferred from structured actions, then from actionable
    audit events. ``owner_hours_saved`` is emitted only when a manual-time
    estimate exists; this prevents an action count from being presented as a
    fabricated time saving.
    """

    events = list(audit_events or ())
    business_action = _mapping(_read(task, "business_action_json", {}))
    explicit = _mapping(business_action.get("outcome_metrics"))
    actions = _structured_actions(business_action)
    action_events = [event for event in events if _is_action_event(event)]

    inferred_total = len(actions) if actions else len(action_events)
    inferred_autonomous = (
        sum(1 for action in actions if _structured_action_is_autonomous(action))
        if actions
        else sum(1 for event in action_events if _is_autonomous_action(event))
    )

    total_value = _first_number(explicit.get("total_actions"), business_action.get("total_actions"))
    autonomous_value = _first_number(
        explicit.get("autonomous_actions"), business_action.get("autonomous_actions")
    )
    total_actions = int(total_value) if total_value is not None else inferred_total
    autonomous_actions = int(autonomous_value) if autonomous_value is not None else inferred_autonomous
    autonomous_actions = min(autonomous_actions, total_actions)

    explicit_owner_minutes = _first_number(
        explicit.get("owner_minutes"), business_action.get("owner_minutes")
    )
    owner_minutes = (
        explicit_owner_minutes
        if explicit_owner_minutes is not None
        else sum(_duration_minutes(_event_payload(event)) for event in events if _is_owner_action(event))
    )

    task_rework = _first_number(_read(task, "rework_cycles", None)) or 0.0
    explicit_rework = _first_number(explicit.get("rework_count"), business_action.get("rework_count")) or 0.0
    event_rework = sum(1 for event in events if _event_type(event) == "owner_rework")
    rework_count = int(max(task_rework, explicit_rework, event_rework))

    explicit_saved = _first_number(
        explicit.get("owner_hours_saved"), business_action.get("owner_hours_saved")
    )
    if explicit_saved is not None:
        owner_hours_saved = explicit_saved
    else:
        manual_estimate = _first_number(
            explicit.get("estimated_manual_minutes"),
            explicit.get("manual_estimate_minutes"),
            business_action.get("estimated_manual_minutes"),
            business_action.get("manual_estimate_minutes"),
        )
        if manual_estimate is None:
            if actions:
                manual_estimate = sum(_manual_estimate_minutes(action) for action in actions)
            else:
                manual_estimate = sum(
                    _manual_estimate_minutes(_event_payload(event))
                    for event in action_events
                    if _is_autonomous_action(event)
                )
        owner_hours_saved = max(0.0, ((manual_estimate or 0.0) - owner_minutes) / 60.0)

    rate = autonomous_actions / total_actions if total_actions else 0.0
    return {
        "owner_minutes": round(owner_minutes, 2),
        "autonomous_actions": autonomous_actions,
        "total_actions": total_actions,
        "rework_count": rework_count,
        "business_outcome": _business_outcome(task, business_action),
        "autonomous_completion_rate": round(rate, 4),
        "owner_hours_saved": round(owner_hours_saved, 4),
    }


compute_outcome_metrics = calculate_outcome_metrics


__all__ = ["calculate_outcome_metrics", "compute_outcome_metrics"]
