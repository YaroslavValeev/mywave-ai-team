# app/presenters/adaptive_decision_support_presenters.py — Phase 12.0
from __future__ import annotations

from typing import Any, List


def present_adaptive_decision_support(raw: dict[str, Any]) -> dict[str, Any]:
    """Compact owner-friendly card. Phase 12.0."""
    if not raw:
        return {}
    do_now = raw.get("do_now")
    return {
        "scope_type": raw.get("scope_type"),
        "scope_key": raw.get("scope_key"),
        "top_problem": raw.get("top_problem", "")[:120],
        "top_action": raw.get("top_action", "")[:80],
        "safe_action_available": raw.get("safe_action_available", False),
        "safe_action_key": raw.get("safe_action_key"),
        "manual_path_required": raw.get("manual_path_required", True),
        "do_now": do_now,
        "do_next": raw.get("do_next"),
        "defer_count": raw.get("defer_count", 0),
        "defer_summary": raw.get("defer_summary", "")[:150],
        "first_step": _first_step_text(do_now),
        "second_step": _first_step_text(raw.get("do_next")),
        "fallback": f"Отложить: {raw.get('defer_count', 0)}" if raw.get("defer_count") else None,
    }


def _first_step_text(iv: dict[str, Any] | None) -> str:
    if not iv:
        return ""
    r = (iv.get("reason") or iv.get("headline", ""))[:80]
    if iv.get("safe_action_key"):
        return f"{r} → /do {iv['safe_action_key']}"
    return r


def present_top_decision_support_items(raw: dict[str, Any]) -> dict[str, Any]:
    """Top items for web. Phase 12.0."""
    items = raw.get("items", [])[:8]
    cards = []
    for i, iv in enumerate(items):
        cards.append({
            "rank": i + 1,
            "reason": (iv.get("reason", ""))[:100],
            "urgency": iv.get("urgency", "medium"),
            "safe_action_key": iv.get("safe_action_key"),
            "safe_action_available": iv.get("safe_action_available", False),
        })
    return {
        "items": cards,
        "count": len(cards),
        "top_problem": raw.get("top_problem", "")[:120],
        "top_action": raw.get("top_action", "")[:80],
        "safe_action_available": raw.get("safe_action_available", False),
        "do_now": raw.get("do_now"),
        "do_next": raw.get("do_next"),
        "defer_count": raw.get("defer_count", 0),
    }


def format_adaptive_decision_support_telegram(raw: dict[str, Any]) -> str:
    """Telegram: compact, first action prominent. Phase 12.0."""
    if not raw:
        return "Нет данных."
    lines = []
    top = raw.get("top_problem", "")
    if top:
        lines.append(f"📌 {top[:80]}")
    action = raw.get("top_action", "")
    if raw.get("safe_action_available") and raw.get("safe_action_key"):
        lines.append(f"→ /do {raw['safe_action_key']}")
    elif action:
        lines.append(f"→ {action[:60]}")
    if raw.get("defer_count", 0) > 0:
        lines.append(f"Отложить: {raw['defer_count']}")
    return "\n".join(lines) if lines else "Нет действий."


def format_top_items_telegram(raw: dict[str, Any]) -> str:
    """Telegram: top decision support items. Phase 12.0/12.3."""
    items = raw.get("items", [])[:5]
    if not items:
        return "Нет приоритетных действий."
    lines = ["🔝 Что делать:"]
    do_now = raw.get("do_now")
    if do_now:
        lines.append(f"1. {do_now.get('reason', '')[:55]}")
        if do_now.get("safe_action_key"):
            lines.append(f"   /do {do_now['safe_action_key']}")
        if do_now.get("intervention_id"):
            lines.append(f"   /defer_intervention {do_now['intervention_id']}")
    do_next = raw.get("do_next")
    if do_next:
        lines.append(f"2. {do_next.get('reason', '')[:55]}")
        if do_next.get("safe_action_key"):
            lines.append(f"   /do {do_next['safe_action_key']}")
        if do_next.get("intervention_id"):
            lines.append(f"   /defer_intervention {do_next['intervention_id']}")
    for i, iv in enumerate(items[2:5], 3):
        lines.append(f"{i}. {iv.get('reason', '')[:50]}")
        if iv.get("intervention_id"):
            lines.append(f"   /defer_intervention {iv['intervention_id']}")
    return "\n".join(lines)
