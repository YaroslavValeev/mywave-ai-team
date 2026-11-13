# app/presenters/role_presenters.py — Phase 9.7: role-scoped presenters (web + Telegram text)
from __future__ import annotations

from typing import Any


def _task_line(t) -> str:
    """Краткая строка по задаче для текста."""
    tid = getattr(t, "id", None) or (t.get("id") if isinstance(t, dict) else None)
    status = getattr(t, "status", None) or (t.get("status") if isinstance(t, dict) else "")
    summary = (getattr(t, "owner_text", None) or getattr(t, "summary", None) or "")[:60]
    if isinstance(t, dict):
        summary = (t.get("owner_text") or t.get("summary") or "")[:60]
    return f"#{tid} {status}: {summary}"


def present_owner_view(data: dict[str, Any]) -> dict[str, Any]:
    """View-model для owner (web). Передаём блоки как есть — шаблон owner_dashboard уже умеет."""
    return data


def present_operator_view(data: dict[str, Any]) -> dict[str, Any]:
    """View-model для operator (web): runtime, blockers, long_running с полями для шаблона."""
    runtime = data.get("runtime", {})
    blockers_raw = data.get("blockers", {})
    long_raw = data.get("long_running", {})
    block_items = []
    for i in blockers_raw.get("items", []):
        t = i.get("task") if isinstance(i, dict) else None
        if t is not None:
            block_items.append({
                "task_id": getattr(t, "id", None),
                "kind": i.get("kind", "blocker"),
                "summary": (getattr(t, "owner_text", None) or getattr(t, "summary", None) or "")[:120],
            })
    long_items = []
    for i in long_raw.get("items", []):
        t = i.get("task")
        if t is not None:
            long_items.append({
                "task_id": getattr(t, "id", None),
                "reason": i.get("reason", ""),
                "age_hours": i.get("age_hours", 0),
                "summary": (getattr(t, "owner_text", None) or getattr(t, "summary", None) or "")[:80],
            })
    out = {
        "runtime": {
            "transport_mode": runtime.get("transport_mode", "?"),
            "molt_ok": runtime.get("molt_ok", False),
            "molt_message": runtime.get("molt_message", ""),
            "state": runtime.get("state", "Unknown"),
            "active_tasks_count": runtime.get("active_tasks_count", 0),
        },
        "blockers_count": blockers_raw.get("blockers_count", 0),
        "degraded_now": blockers_raw.get("degraded_now", False),
        "blockers": block_items,
        "long_running_count": long_raw.get("count", 0),
        "long_running": long_items,
    }
    if data.get("domain_recommendations"):
        out["domain_recommendations"] = data["domain_recommendations"]
    if data.get("collaboration_summary"):
        out["collaboration_summary"] = data["collaboration_summary"]
    return out


def present_executor_view(data: dict[str, Any]) -> dict[str, Any]:
    """View-model для executor (web): active tasks, recent artifacts, blockers. Phase 10.3: + domain_recommendations."""
    tasks = data.get("active_tasks", [])
    artifacts = data.get("recent_artifacts", [])
    blockers_raw = data.get("blockers", {})
    task_items = []
    for t in tasks:
        task_items.append({
            "task_id": getattr(t, "id", None),
            "status": getattr(t, "status", ""),
            "summary": (getattr(t, "owner_text", None) or getattr(t, "summary", None) or "")[:120],
        })
    art_items = []
    for t in artifacts:
        art_items.append({
            "task_id": getattr(t, "id", None),
            "summary": (getattr(t, "summary", None) or getattr(t, "report_path", None) or "")[:150],
            "report_path": getattr(t, "report_path", None),
        })
    block_items = []
    for i in blockers_raw.get("items", []):
        t = i.get("task") if isinstance(i, dict) else None
        if t is not None:
            block_items.append({
                "task_id": getattr(t, "id", None),
                "kind": i.get("kind", "blocker"),
                "summary": (getattr(t, "owner_text", None) or getattr(t, "summary", None) or "")[:100],
            })
    out = {
        "active_tasks": task_items,
        "recent_artifacts": art_items,
        "blockers_count": blockers_raw.get("blockers_count", 0),
        "blockers": block_items,
    }
    if data.get("domain_recommendations"):
        out["domain_recommendations"] = data["domain_recommendations"]
    if data.get("collaboration_summary"):
        out["collaboration_summary"] = data["collaboration_summary"]
    return out


def present_reviewer_view(data: dict[str, Any]) -> dict[str, Any]:
    """View-model для reviewer (web): pending approvals, decision queue."""
    pending = data.get("pending_approvals", [])
    awaiting = data.get("awaiting_decisions", {})
    queue_raw = data.get("decision_queue", {})
    pending_items = []
    for t in pending:
        pending_items.append({
            "task_id": getattr(t, "id", None),
            "status": getattr(t, "status", ""),
            "summary": (getattr(t, "owner_text", None) or getattr(t, "summary", None) or "")[:150],
        })
    queue_items = []
    for q in queue_raw.get("items", []):
        queue_items.append({
            "task_id": q.get("task_id"),
            "reason": q.get("reason", ""),
            "priority": q.get("priority", ""),
            "suggested_next_action": q.get("suggested_next_action", ""),
        })
    out = {
        "pending_count": len(pending) or awaiting.get("pending_count", 0),
        "pending_approvals": pending_items,
        "decision_queue_count": queue_raw.get("count", 0),
        "decision_queue": queue_items,
    }
    if data.get("domain_recommendations"):
        out["domain_recommendations"] = data["domain_recommendations"]
    if data.get("collaboration_summary"):
        out["collaboration_summary"] = data["collaboration_summary"]
    return out


def format_owner_view_text(data: dict[str, Any], max_lines: int = 25) -> str:
    """Компактный текстовый summary для owner (Telegram)."""
    ov = data.get("overview", {})
    lines = [
        "👤 Owner view",
        f"State: {ov.get('state', '?')} | Molt: {'✓' if ov.get('molt_ok') else '✗'}",
        f"Active: {ov.get('active_tasks_count', 0)} | Pending approvals: {ov.get('pending_approvals_count', 0)}",
    ]
    next_actions = data.get("next_actions", {}).get("items", [])[:5]
    if next_actions:
        lines.append("Next:")
        for a in next_actions[:5]:
            lines.append(f"  #{a.get('task_id', '?')} {a.get('priority', '')}: {a.get('suggested_action', '')[:50]}")
    blockers = data.get("blockers", {}).get("blockers_count", 0)
    if blockers > 0:
        lines.append(f"Blockers: {blockers}")
    dr = data.get("domain_recommendations", {})
    if dr and dr.get("recommended_domains"):
        lines.append("Domain focus: " + ", ".join(dr["recommended_domains"][:5]))
    collab = data.get("collaboration_summary", {})
    if collab and collab.get("collaboration_items"):
        items = collab["collaboration_items"][:3]
        lines.append("Collaboration: " + "; ".join(
            f"{i.get('target_role', '?')}: {i.get('reason', '')[:30]}" for i in items
        ))
    return "\n".join(lines[:max_lines])


def format_operator_view_text(data: dict[str, Any], max_lines: int = 20) -> str:
    """Компактный текстовый summary для operator (Telegram)."""
    r = data.get("runtime", {})
    lines = [
        "⚙️ Operator view",
        f"State: {r.get('state', '?')} | Molt: {'✓' if r.get('molt_ok') else '✗'} ({r.get('molt_message', '')})",
        f"Transport: {r.get('transport_mode', '?')} | Active tasks: {r.get('active_tasks_count', 0)}",
    ]
    blockers = data.get("blockers", {})
    if blockers.get("degraded_now"):
        lines.append("⚠️ DEGRADED")
    bc = blockers.get("blockers_count", 0)
    if bc > 0:
        lines.append(f"Blockers: {bc}")
    long_running = data.get("long_running", {}).get("items", [])[:3]
    if long_running:
        lines.append("Stuck/long-running:")
        for i in long_running[:3]:
            t = i.get("task")
            if t:
                lines.append(f"  #{getattr(t, 'id', '?')} {i.get('reason', '')} ({i.get('age_hours', 0)}h)")
    dr = data.get("domain_recommendations", {})
    if dr and dr.get("recommended_domains"):
        lines.append("Domain pressure: " + ", ".join(dr["recommended_domains"][:3]))
    collab = data.get("collaboration_summary", {})
    if collab and collab.get("collaboration_items"):
        items = collab["collaboration_items"][:3]
        lines.append("Collaboration: " + "; ".join(
            f"{i.get('target_role', '?')}: {i.get('reason', '')[:30]}" for i in items
        ))
    return "\n".join(lines[:max_lines])


def format_executor_view_text(data: dict[str, Any], max_lines: int = 20) -> str:
    """Компактный текстовый summary для executor (Telegram)."""
    tasks = data.get("active_tasks", [])[:5]
    artifacts = data.get("recent_artifacts", [])[:3]
    blockers = data.get("blockers", {})
    lines = [
        "🔧 Executor view",
        f"Active tasks: {len(tasks)} | Blockers: {blockers.get('blockers_count', 0)}",
    ]
    if tasks:
        lines.append("Active:")
        for t in tasks[:5]:
            lines.append(f"  {_task_line(t)}")
    if artifacts:
        lines.append("Recent artifacts:")
        for t in artifacts[:3]:
            lines.append(f"  #{getattr(t, 'id', '?')} {(getattr(t, 'summary', None) or getattr(t, 'report_path', '') or '')[:50]}")
    dr = data.get("domain_recommendations", {})
    if dr and dr.get("recommended_domains"):
        lines.append("Domain focus: " + ", ".join(dr["recommended_domains"][:3]))
    collab = data.get("collaboration_summary", {})
    if collab and collab.get("collaboration_items"):
        items = collab["collaboration_items"][:3]
        lines.append("Collaboration: " + "; ".join(
            f"{i.get('target_role', '?')}: {i.get('reason', '')[:30]}" for i in items
        ))
    return "\n".join(lines[:max_lines])


def format_reviewer_view_text(data: dict[str, Any], max_lines: int = 20) -> str:
    """Компактный текстовый summary для reviewer (Telegram)."""
    pending = data.get("pending_approvals", [])[:5]
    queue = data.get("decision_queue", {}).get("items", [])[:5]
    lines = [
        "📋 Reviewer view",
        f"Pending approvals: {len(pending)} | Decision queue: {len(queue)}",
    ]
    if pending:
        lines.append("Pending:")
        for t in pending[:5]:
            lines.append(f"  {_task_line(t)}")
    if queue:
        lines.append("Queue:")
        for q in queue[:5]:
            lines.append(f"  #{q.get('task_id', '?')} {q.get('reason', '')[:40]}")
    if len(lines) == 2:
        lines.append("Нет ожидающих решений.")
    dr = data.get("domain_recommendations", {})
    if dr and dr.get("recommended_domains"):
        lines.append("Domain focus: " + ", ".join(dr["recommended_domains"][:3]))
    collab = data.get("collaboration_summary", {})
    if collab and collab.get("collaboration_items"):
        items = collab["collaboration_items"][:3]
        lines.append("Collaboration: " + "; ".join(
            f"{i.get('target_role', '?')}: {i.get('reason', '')[:30]}" for i in items
        ))
    return "\n".join(lines[:max_lines])
