# app/presenters/collaboration_execution_presenters.py — Phase 11.4
from __future__ import annotations

from typing import Any, List


def present_collaboration_execution_card(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {}
    return {
        "execution_id": raw.get("execution_id", ""),
        "execution_type": raw.get("execution_type", ""),
        "subject_type": raw.get("subject_type", ""),
        "subject_key": raw.get("subject_key", ""),
        "source_role": raw.get("source_role", ""),
        "target_role": raw.get("target_role", ""),
        "execution_status": raw.get("execution_status", ""),
        "execution_reason": (raw.get("execution_reason") or "")[:200],
        "safe_action_key": raw.get("safe_action_key"),
        "last_action_result": (raw.get("last_action_result") or "")[:200] if raw.get("last_action_result") else None,
        "suggestion_fingerprint": raw.get("suggestion_fingerprint"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "closed_at": raw.get("closed_at"),
        "closure_reason": raw.get("closure_reason"),
        "actor": raw.get("actor"),
    }


def present_collaboration_execution_list(items: List[dict]) -> dict[str, Any]:
    cards = [present_collaboration_execution_card(i) for i in (items or [])]
    return {"items": cards, "count": len(cards)}


def present_collaboration_execution_summary(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {}
    return {
        "window_days": raw.get("window_days", 7),
        "pending_count": raw.get("pending_count", 0),
        "closed_count": raw.get("closed_count", 0),
        "total_recent": raw.get("total_recent", 0),
        "explainable": raw.get("explainable", True),
    }


def present_collaboration_execution_result(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {"success": False}
    return {
        "success": True,
        "execution": present_collaboration_execution_card(raw),
    }


def format_collaboration_executions_telegram(items: List[dict[str, Any]], limit: int = 8) -> str:
    if not items:
        return "Collaboration executions: пусто."
    lines = ["Collaboration executions:"]
    for e in items[:limit]:
        c = present_collaboration_execution_card(e)
        lines.append(f"  • {c.get('execution_id')}: {c.get('execution_status')} — {(c.get('execution_reason') or '')[:45]}")
    return "\n".join(lines)


def format_collaboration_execution_card_telegram(raw: dict[str, Any]) -> str:
    c = present_collaboration_execution_card(raw)
    if not c.get("execution_id"):
        return "Execution не найден."
    lines = [
        f"Execution: {c.get('execution_id')}",
        f"Status: {c.get('execution_status')}",
        f"Type: {c.get('execution_type')}",
        f"Subject: {c.get('subject_type')}/{c.get('subject_key')}",
        f"Reason: {(c.get('execution_reason') or '')[:100]}",
    ]
    if c.get("safe_action_key"):
        lines.append(f"Safe action: {c.get('safe_action_key')}")
    if c.get("last_action_result"):
        lines.append(f"Last result: {(c.get('last_action_result') or '')[:80]}")
    return "\n".join(lines)
