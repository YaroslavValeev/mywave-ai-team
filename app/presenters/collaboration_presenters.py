# app/presenters/collaboration_presenters.py — Phase 10.9: collaboration view-models
from __future__ import annotations

from typing import Any, List


def present_task_handoff_signals(raw: dict[str, Any]) -> dict[str, Any]:
    """Task handoff signals для web."""
    if not raw:
        return {}
    return {
        "task_id": raw.get("task_id"),
        "task_status": raw.get("task_status"),
        "handoff_signals": raw.get("handoff_signals", []),
        "project_key": raw.get("project_key"),
        "error": raw.get("error"),
    }


def present_project_handoff_signals(raw: dict[str, Any]) -> dict[str, Any]:
    """Project handoff signals для web."""
    if not raw:
        return {}
    return {
        "project_key": raw.get("project_key"),
        "handoff_signals": raw.get("handoff_signals", []),
        "pending_count": raw.get("pending_count"),
        "risks_count": raw.get("risks_count"),
    }


def present_role_collaboration_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Role collaboration summary для web."""
    if not raw:
        return {}
    return {
        "role_key": raw.get("role_key"),
        "collaboration_items": raw.get("collaboration_items", []),
        "count": raw.get("count", 0),
    }


def present_cross_role_handoffs(items: List[dict[str, Any]]) -> dict[str, Any]:
    """Cross-role handoffs для web."""
    return {"items": list(items), "count": len(items)}


def present_collaboration_hotspots(items: List[dict[str, Any]]) -> dict[str, Any]:
    """Collaboration hotspots для web."""
    return {"items": list(items), "count": len(items)}


def present_collaboration_recommendations(items: List[dict[str, Any]]) -> dict[str, Any]:
    """Collaboration recommendations для web."""
    return {"items": list(items), "count": len(items)}


def format_collaboration_telegram(hotspots: List[dict], recs: List[dict]) -> str:
    """Краткий текст collaboration для Telegram."""
    lines = ["Collaboration:"]
    for h in hotspots[:5]:
        lines.append(f"  {h.get('hotspot_type', '?')}: {h.get('reason', '')[:60]}")
    for r in recs[:3]:
        lines.append(f"  → {r.get('target_role', '?')}: {r.get('recommended_action', '')[:50]}")
    if not hotspots and not recs:
        lines.append("  Нет активных сигналов.")
    return "\n".join(lines)


def format_handoffs_telegram(handoffs: List[dict]) -> str:
    """Cross-role handoffs для Telegram."""
    lines = ["Handoffs:"]
    for h in handoffs[:8]:
        ht = h.get("handoff_type", "?")
        reason = h.get("reason", "")[:40]
        tid = h.get("task_id")
        suf = f" task #{tid}" if tid else ""
        lines.append(f"  {ht}{suf}: {reason}")
    if not handoffs:
        lines.append("  Нет активных handoff.")
    return "\n".join(lines)


def format_project_handoffs_telegram(raw: dict[str, Any]) -> str:
    """Project handoff signals для Telegram."""
    pk = raw.get("project_key", "?")
    signals = raw.get("handoff_signals", [])
    lines = [f"Project {pk} handoffs:"]
    for s in signals[:5]:
        lines.append(f"  {s.get('handoff_type', '?')} → {s.get('target_role', '?')}: {s.get('handoff_reason', '')[:50]}")
    if not signals:
        lines.append("  Нет сигналов.")
    return "\n".join(lines)


def format_role_collaboration_telegram(raw: dict[str, Any]) -> str:
    """Role collaboration для Telegram."""
    role = raw.get("role_key", "?")
    items = raw.get("collaboration_items", [])
    lines = [f"Role {role} collaboration:"]
    for i in items[:5]:
        lines.append(f"  {i.get('handoff_type', '?')}: {i.get('reason', '')[:50]}")
    if not items:
        lines.append("  Нет активных items.")
    return "\n".join(lines)
