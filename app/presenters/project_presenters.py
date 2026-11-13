# app/presenters/project_presenters.py — Phase 9.5: view-models for project drill-down
from __future__ import annotations

from typing import Any


def present_project_list(raw: dict[str, Any]) -> dict[str, Any]:
    """Список проектов для web / text."""
    items = raw.get("items", [])
    return {
        "items": [
            {
                "project_key": p.get("project_key", ""),
                "project_label": p.get("project_label", p.get("project_key", "")),
                "status": p.get("status", "healthy"),
                "reason": p.get("reason", ""),
                "active_count": p.get("active_count", 0),
                "pending_count": p.get("pending_count", 0),
                "rework_signals": p.get("rework_signals", 0),
                "long_running": p.get("long_running", 0),
                "dominant_domain": p.get("dominant_domain"),
            }
            for p in items
        ],
        "count": raw.get("count", len(items)),
    }


def present_project_overview(raw: dict[str, Any]) -> dict[str, Any]:
    """Overview одного проекта. Phase 10.3: + domain_profile."""
    out = {
        "project_key": raw.get("project_key", ""),
        "project_label": raw.get("project_label", raw.get("project_key", "")),
        "health": raw.get("health", {}),
        "active_count": raw.get("active_count", 0),
        "pending_count": raw.get("pending_count", 0),
        "recent_artifacts_count": raw.get("recent_artifacts_count", 0),
    }
    if raw.get("domain_profile"):
        out["domain_profile"] = raw["domain_profile"]
    return out


def present_project_health(raw: dict[str, Any]) -> dict[str, Any]:
    """Health одного проекта."""
    return {
        "project_key": raw.get("project_key", ""),
        "project_label": raw.get("project_label", raw.get("project_key", "")),
        "status": raw.get("status", "healthy"),
        "reason": raw.get("reason", ""),
        "active_count": raw.get("active_count", 0),
        "pending_count": raw.get("pending_count", 0),
        "rework_signals": raw.get("rework_signals", 0),
        "long_running": raw.get("long_running", 0),
    }


def present_project_tasks(raw: dict[str, Any]) -> dict[str, Any]:
    """Задачи проекта — сериализация для web."""
    items = raw.get("items", [])
    out = []
    for t in items:
        if hasattr(t, "id"):
            updated = getattr(t, "updated_at", None)
            out.append({
                "id": getattr(t, "id", None),
                "status": getattr(t, "status", ""),
                "domain": getattr(t, "domain", "") or "",
                "owner_text": (getattr(t, "owner_text", None) or "")[:150],
                "updated_at": updated.isoformat() if updated else None,
            })
        elif isinstance(t, dict):
            out.append(t)
    return {"items": out, "count": len(out)}


def present_project_approvals(raw: dict[str, Any]) -> dict[str, Any]:
    """Approvals проекта — сериализация."""
    items = raw.get("items", [])
    out = []
    for t in items:
        if hasattr(t, "id"):
            out.append({
                "id": getattr(t, "id", None),
                "status": getattr(t, "status", ""),
                "owner_text": (getattr(t, "owner_text", None) or "")[:200],
            })
        elif isinstance(t, dict):
            out.append(t)
    return {"items": out, "count": raw.get("count", len(out))}


def present_project_artifacts(raw: dict[str, Any]) -> dict[str, Any]:
    """Артефакты уже в виде dict в raw."""
    items = raw.get("items", [])
    return {"items": list(items), "count": raw.get("count", len(items))}


def present_project_risks(raw: dict[str, Any]) -> dict[str, Any]:
    """Риски проекта."""
    items = raw.get("items", [])
    return {
        "items": [
            {
                "risk_type": r.get("risk_type", ""),
                "reason": r.get("reason", ""),
                "suggested_action": r.get("suggested_action", ""),
            }
            for r in items
        ],
        "count": raw.get("count", len(items)),
    }


def present_project_decision_queue(raw: dict[str, Any]) -> dict[str, Any]:
    """Очередь решений проекта."""
    items = raw.get("items", [])
    return {
        "items": [
            {
                "task_id": q.get("task_id"),
                "reason": q.get("reason", ""),
                "priority": q.get("priority", ""),
                "suggested_next_action": q.get("suggested_next_action", ""),
                "if_ignored": q.get("if_ignored", ""),
            }
            for q in items
        ],
        "count": raw.get("count", len(items)),
    }


def format_project_list_text(data: dict[str, Any]) -> str:
    """Текст для Telegram /projects."""
    items = data.get("items", [])
    if not items:
        return "Проекты: нет групп с задачами (или все в general).\nИспользуйте /project general для сводки."
    lines = ["📁 Проекты (project_key · health · active · pending):"]
    for p in items:
        status_emoji = "🔴" if p.get("status") == "critical" else ("🟠" if p.get("status") == "attention_needed" else "🟢")
        dom = p.get("dominant_domain")
        suf = f" · dom: {dom}" if dom else ""
        lines.append(f"{status_emoji} {p.get('project_label', p.get('project_key', '?'))} — {p.get('status', '?')} · active: {p.get('active_count', 0)} · pending: {p.get('pending_count', 0)}{suf}")
    lines.append("\nПодробнее: /project <key> или Dashboard → /owner/projects")
    return "\n".join(lines)


def format_project_card_text(data: dict[str, Any]) -> str:
    """Текст для Telegram /project <key>."""
    overview = data.get("overview", {})
    project_key = overview.get("project_key", data.get("project_key", "?"))
    health = data.get("health", overview.get("health", {}))
    status = health.get("status", "?")
    status_emoji = "🔴" if status == "critical" else ("🟠" if status == "attention_needed" else "🟢")
    lines = [
        f"📁 Проект: {overview.get('project_label', project_key)}",
        f"{status_emoji} Health: {status} — {health.get('reason', '')}",
        f"Active: {overview.get('active_count', 0)} · Pending: {overview.get('pending_count', 0)} · Artifacts: {overview.get('recent_artifacts_count', 0)}",
    ]
    dp = overview.get("domain_profile")
    if dp and dp.get("dominant_domain"):
        lines.append(f"Доминирующий домен: {dp.get('dominant_domain')}" + (f" · {', '.join(dp.get('secondary_domains', [])[:2])}" if dp.get("secondary_domains") else ""))
        if dp.get("mismatch_signals"):
            lines.append("Сигналы: " + " | ".join([s.get("reason", s.get("type", "")) for s in dp["mismatch_signals"][:2]]))
    if data.get("risks", {}).get("items"):
        lines.append("Risks: " + str(len(data["risks"]["items"])))
    if data.get("decision_queue", {}).get("items"):
        lines.append("Decision queue: " + str(len(data["decision_queue"]["items"])))
    lines.append(f"Dashboard: /owner/project/{project_key}")
    return "\n".join(lines)
