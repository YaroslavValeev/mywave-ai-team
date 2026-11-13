# app/presenters/owner_presenters.py — Phase 9.0: human-readable formatting for owner commands
from __future__ import annotations

from typing import Any, List


def format_summary(data: dict[str, Any]) -> str:
    """Форматирование краткой сводки для /status."""
    lines = [
        "📊 Status",
        f"Mode: {data.get('transport_mode', 'local')}",
        f"Molt: {data.get('molt_message', 'n/a')}",
        f"Active tasks: {data.get('active_tasks_count', 0)}",
        f"Pending approvals: {data.get('pending_approvals_count', 0)}",
        f"Recent artifacts: {data.get('recent_artifacts_count', 0)}",
        f"State: {data.get('state', 'OK')}",
    ]
    return "\n".join(lines)


def format_task_card(card: dict[str, Any]) -> str:
    """Форматирование карточки задачи для /task <id>. Включает domain hint (Phase 10.0)."""
    task = card.get("task")
    if not task:
        return "Задача не найдена."
    run_id = card.get("run_id") or "—"
    approval = "да" if card.get("approval_id") else "нет"
    last = card.get("last_event") or "—"
    report = (task.report_path or "")[:80] if task.report_path else "—"
    summary = (task.summary or "")[:150] + "…" if task.summary and len(task.summary) > 150 else (task.summary or "—")
    lines = [
        f"Task #{task.id}",
        f"Status: {task.status}",
        f"Run: {run_id}",
        f"Waiting approval: {approval}",
        f"Last event: {last}",
        f"Report: {report}",
        f"Summary: {summary}",
    ]
    dm = card.get("domain_metadata")
    edc = card.get("effective_domain_context")
    if edc and edc.get("selected_primary_domain"):
        lines.append(f"Экспертиза: {edc.get('selected_primary_domain')}")
        if edc.get("domain_override"):
            lines.append("Override: yes (owner)")
            if edc.get("domain_override_reason"):
                lines.append(f"Причина: {edc.get('domain_override_reason')[:80]}")
    elif dm and dm.get("primary_domain"):
        hint = format_domain_hint_compact(dm)
        if hint:
            lines.append(hint)
    spec = card.get("specialization_context")
    if spec and spec.get("profile_name"):
        lines.append(f"Профиль (pipeline): {spec.get('profile_name')}" + (" (fallback)" if spec.get("fallback_used") else ""))
    return "\n".join(lines)


def format_domain_hint_compact(domain_metadata: dict[str, Any]) -> str:
    """Компактная строка domain hint для карточки/списка (Phase 10.0)."""
    if not domain_metadata:
        return ""
    primary = domain_metadata.get("primary_domain")
    if not primary:
        return ""
    reason = (domain_metadata.get("domain_reason") or "")[:80]
    return f"Экспертиза: {primary}" + (f" — {reason}" if reason else "")


def format_approvals_list(tasks: List[Any]) -> str:
    """Форматирование списка ожидающих approve."""
    if not tasks:
        return "Нет ожидающих approve."
    lines = ["Ожидающие решения:"]
    for t in tasks:
        lines.append(f"  #{t.id} — {t.status} — {(t.owner_text or '')[:50]}…" if (t.owner_text and len(t.owner_text) > 50) else f"  #{t.id} — {t.status} — {t.owner_text or ''}")
    return "\n".join(lines)


def format_artifacts_list(tasks: List[Any]) -> str:
    """Форматирование списка последних артефактов."""
    if not tasks:
        return "Нет артефактов."
    lines = ["Последние результаты:"]
    for t in tasks:
        path = t.report_path or "(summary)"
        lines.append(f"  Task #{t.id} — {path} — {(t.summary or '')[:40]}…" if t.summary and len(t.summary) > 40 else f"  Task #{t.id} — {path} — {t.summary or ''}")
    return "\n".join(lines)


def format_tasks_list(tasks: List[Any]) -> str:
    """Форматирование списка задач."""
    if not tasks:
        return "Нет активных задач."
    lines = ["Задачи:"]
    for t in tasks:
        lines.append(f"  #{t.id} — {t.status} — {(t.owner_text or '')[:45]}…" if t.owner_text and len(t.owner_text) > 45 else f"  #{t.id} — {t.status} — {t.owner_text or ''}")
    return "\n".join(lines)


def format_runs_list(runs: List[dict]) -> str:
    """Форматирование сводки по runs."""
    if not runs:
        return "Нет активных run."
    lines = ["Runs:"]
    for r in runs:
        t = r.get("task")
        if t:
            lines.append(f"  Task #{t.id} — {r.get('run_id', '—')} — {r.get('canonical_status', '')}")
    return "\n".join(lines)


def format_detailed_summary(data: dict[str, Any]) -> str:
    """Форматирование детальной сводки для /summary."""
    parts = [format_summary(data)]
    if data.get("pending_approvals_list"):
        parts.append(format_approvals_list(data["pending_approvals_list"]))
    if data.get("top_tasks"):
        parts.append("Active: " + ", ".join(f"#{t.id}" for t in data["top_tasks"][:5]))
    if data.get("recent_artifacts_list"):
        parts.append(format_artifacts_list(data["recent_artifacts_list"]))
    return "\n\n".join(parts)
