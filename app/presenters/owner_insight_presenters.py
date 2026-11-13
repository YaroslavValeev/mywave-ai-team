from __future__ import annotations

from typing import Any


def format_weekly_digest(data: dict[str, Any]) -> str:
    lines = [
        "🗓 Weekly Digest",
        f"Completed: {data.get('completed_count', 0)}",
        f"Approvals: {data.get('approvals_count', 0)}",
        f"Rework: {data.get('rework_count', 0)}",
        f"Pending approvals: {data.get('pending_approvals_count', 0)}",
        f"Blockers: {data.get('blockers_count', 0)}",
        f"Degraded signals (7d): {data.get('degraded_events_count', 0)}",
        f"Owner focus: {data.get('owner_focus', 'n/a')}",
    ]
    return "\n".join(lines)


def format_blockers_summary(data: dict[str, Any]) -> str:
    lines = [f"🚧 Blockers: {data.get('blockers_count', 0)}"]
    if data.get("degraded_now"):
        lines.append("⚠️ Сейчас система в degraded mode.")
    items = data.get("items") or []
    for i in items[:5]:
        t = i.get("task")
        if not t:
            continue
        lines.append(f"- #{t.id} {t.status} ({i.get('kind', 'blocker')})")
    if len(lines) == 1:
        lines.append("Критичных блокеров сейчас нет.")
    return "\n".join(lines)


def format_awaiting_decisions_summary(data: dict[str, Any]) -> str:
    lines = [f"⏳ Awaiting decisions: {data.get('pending_count', 0)}"]
    for t in (data.get("items") or [])[:7]:
        lines.append(f"- #{t.id} {t.status}: {(t.owner_text or '')[:60]}")
    if len(lines) == 1:
        lines.append("Нет задач, ожидающих решения owner.")
    return "\n".join(lines)


def format_completed_recently_summary(data: dict[str, Any]) -> str:
    lines = [
        f"✅ Completed recently (7d): {data.get('completed_count', 0)}",
        f"Artifacts ready: {data.get('artifact_count', 0)}",
    ]
    for t in (data.get("items") or [])[:5]:
        lines.append(f"- #{t.id} DONE: {(t.summary or t.report_path or '')[:60]}")
    return "\n".join(lines)


def format_project_activity_summary(data: dict[str, Any]) -> str:
    lines = [f"📁 Project activity groups: {data.get('projects_count', 0)}"]
    for p in (data.get("top_projects") or [])[:5]:
        lines.append(f"- {p.get('project')}: {p.get('tasks_count')} tasks")
    return "\n".join(lines)


def format_rework_signal_summary(data: dict[str, Any]) -> str:
    lines = [f"🔁 Rework signals: {data.get('count', 0)}"]
    for t in (data.get("items") or [])[:5]:
        lines.append(f"- #{t.id} cycles={getattr(t, 'rework_cycles', 0)} status={t.status}")
    if len(lines) == 1:
        lines.append("Повторных rework сигналов не найдено.")
    return "\n".join(lines)


def format_degraded_signal_summary(data: dict[str, Any]) -> str:
    lines = [
        f"⚠️ Degraded state now: {data.get('current_state', 'OK')}",
        f"Signals 7d: {data.get('events_count_7d', 0)}",
    ]
    for e in (data.get("events") or [])[:5]:
        lines.append(f"- {e.get('event_type')} (task={e.get('task_id')})")
    return "\n".join(lines)


def format_long_running_summary(data: dict[str, Any]) -> str:
    lines = [f"🕒 Long-running/stale: {data.get('count', 0)}"]
    for i in (data.get("items") or [])[:5]:
        t = i.get("task")
        if not t:
            continue
        lines.append(f"- #{t.id} {t.status}, {i.get('age_hours', 0)}h ({i.get('reason')})")
    if len(lines) == 1:
        lines.append("Долгих зависаний не обнаружено.")
    return "\n".join(lines)
