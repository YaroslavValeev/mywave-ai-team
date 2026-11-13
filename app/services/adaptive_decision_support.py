# app/services/adaptive_decision_support.py — Phase 12.0: polished decision support
from __future__ import annotations

from typing import Any, List, Optional

from app.services.intervention_planning import (
    get_intervention_bundle,
    get_task_intervention_plan,
    get_portfolio_intervention_plan,
    get_cross_layer_intervention_plans,
    list_priority_interventions,
)


def _priority_value(urgency: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(urgency, 1)


def _preferred_do_now(interventions: List[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Preferred do_now by INTERVENTION_SEQUENCE_POLICY: safe action first, then urgency."""
    if not interventions:
        return None
    with_safe = [i for i in interventions if i.get("safe_action_available")]
    if with_safe:
        with_safe.sort(key=lambda x: _priority_value(x.get("urgency", "medium")))
        return with_safe[0]
    interventions.sort(key=lambda x: (_priority_value(x.get("urgency", "medium")), x.get("intervention_type", "")))
    return interventions[0]


def _to_adaptive_bundle(plan: dict[str, Any], scope_type: str, scope_key: str = "") -> dict[str, Any]:
    """Convert intervention plan to adaptive decision support format."""
    interventions = plan.get("interventions", [])
    try:
        from app.services.intervention_acceptance import get_recently_deferred_ids
        deferred_ids = get_recently_deferred_ids(hours=24)
        interventions = [i for i in interventions if i.get("intervention_id") not in deferred_ids]
    except Exception:
        pass
    do_now = _preferred_do_now(interventions)
    rest = [i for i in interventions if i != do_now] if interventions else []
    do_next = rest[0] if rest else None
    defer = rest[1:] if len(rest) > 1 else []

    top_problem = (do_now or {}).get("reason", "")[:120] if do_now else ""
    safe_key = (do_now or {}).get("safe_action_key") if do_now else None
    top_action = f"/do {safe_key}" if safe_key else ((do_now or {}).get("suggested_action", "") or "/owner/interventions")[:80]

    return {
        "scope_type": scope_type,
        "scope_key": scope_key,
        "top_problem": top_problem,
        "top_action": top_action,
        "safe_action_available": bool(safe_key),
        "safe_action_key": safe_key,
        "manual_path_required": not bool(safe_key),
        "do_now": do_now,
        "do_next": do_next,
        "defer_count": len(defer),
        "defer_summary": "; ".join((d.get("reason", "")[:40] for d in defer[:3])) if defer else "",
        "evidence_trail": [r.get("id_value", "") for r in plan.get("evidence_refs", [])[:5]],
        "plan_headline": plan.get("plan_headline", ""),
        "plan_reason": plan.get("plan_reason", ""),
    }


def get_task_decision_support(task_id: int, window_days: int = 7) -> dict[str, Any]:
    """Task-level adaptive decision support. Phase 12.0."""
    plan = get_task_intervention_plan(task_id, window_days=window_days)
    return _to_adaptive_bundle(plan, "task", str(task_id))


def get_project_decision_support(project_key: str, window_days: int = 30) -> dict[str, Any]:
    """Project-level adaptive decision support. Phase 12.0."""
    bundle = get_intervention_bundle("project", scope_key=project_key, window_days=window_days)
    plan = bundle.get("plan", {})
    return _to_adaptive_bundle(plan, "project", project_key)


def get_portfolio_decision_support(window_days: int = 30) -> dict[str, Any]:
    """Portfolio-level adaptive decision support. Phase 12.0."""
    plan = get_portfolio_intervention_plan(window_days=window_days)
    return _to_adaptive_bundle(plan, "portfolio", "")


def get_cross_layer_decision_support(window_days: int = 30) -> dict[str, Any]:
    """Cross-layer adaptive decision support. Phase 12.0."""
    plan = get_cross_layer_intervention_plans(window_days=window_days)
    return _to_adaptive_bundle(plan, "cross_layer", "")


def list_top_decision_support_items(window_days: int = 30, limit: int = 8) -> dict[str, Any]:
    """Top decision support items across portfolio + cross-layer. Phase 12.0."""
    raw = list_priority_interventions(window_days=window_days, limit=limit)
    items = raw.get("items", [])
    try:
        from app.services.intervention_acceptance import get_recently_deferred_ids
        deferred_ids = get_recently_deferred_ids(hours=24)
        items = [i for i in items if i.get("intervention_id") not in deferred_ids]
    except Exception:
        pass
    with_safe = [i for i in items if i.get("safe_action_available")]
    rest = [i for i in items if not i.get("safe_action_available")]
    sorted_items = sorted(with_safe, key=lambda x: _priority_value(x.get("urgency", "medium")))
    sorted_items += sorted(rest, key=lambda x: _priority_value(x.get("urgency", "medium")))
    do_now = sorted_items[0] if sorted_items else None
    do_next = sorted_items[1] if len(sorted_items) > 1 else None
    defer = sorted_items[2:limit]
    return {
        "items": sorted_items[:limit],
        "count": len(sorted_items[:limit]),
        "window_days": window_days,
        "top_problem": (do_now or {}).get("reason", "")[:120] if do_now else "",
        "top_action": f"/do {(do_now or {}).get('safe_action_key')}" if (do_now or {}).get("safe_action_key") else ((do_now or {}).get("reason", "")[:60] if do_now else ""),
        "safe_action_available": bool((do_now or {}).get("safe_action_available")),
        "do_now": do_now,
        "do_next": do_next,
        "defer_count": len(defer),
    }
