# app/presenters/owner_recommendation_presenters.py — Phase 9.3: strategic digest and recommendation formatting
from __future__ import annotations

from typing import Any


def format_next_actions(data: dict[str, Any]) -> str:
    """Следующие шаги для owner: что делать, почему, что будет при откладывании."""
    items = data.get("items") or []
    if not items:
        return "✅ Нет срочных действий. Можно планировать следующие задачи."
    lines = ["🎯 Next actions:"]
    for i, a in enumerate(items[:5], 1):
        tid = a.get("task_id")
        part = f"{i}. [{a.get('priority', 'medium')}] {a.get('suggested_action', '')}"
        if tid:
            part = f"{i}. Task #{tid} — {a.get('suggested_action', '')}"
        lines.append(part)
        lines.append(f"   Почему: {a.get('reason', '')}")
        if a.get("if_deferred"):
            lines.append(f"   Если отложить: {a['if_deferred']}")
    return "\n".join(lines)


def format_decision_queue(data: dict[str, Any]) -> str:
    """Очередь решений: приоритет, причина, следующий шаг, последствия игнора."""
    items = data.get("items") or []
    if not items:
        return "Очередь решений пуста."
    lines = ["📋 Decision queue:"]
    for i, q in enumerate(items[:10], 1):
        tid = q.get("task_id")
        label = f"Task #{tid}" if tid else "System"
        lines.append(f"{i}. {label} — {q.get('reason', '')}")
        lines.append(f"   Действие: {q.get('suggested_next_action', '')}")
        if q.get("if_ignored"):
            lines.append(f"   Если игнорировать: {q['if_ignored']}")
    return "\n".join(lines)


def format_project_health_summary(data: dict[str, Any]) -> str:
    """Project health по группам: healthy / attention_needed / critical."""
    items = data.get("items") or []
    if not items:
        return "Нет групповых данных."
    lines = ["📁 Project health:"]
    for p in items[:10]:
        status_emoji = "🟢" if p.get("status") == "healthy" else ("🟡" if p.get("status") == "attention_needed" else "🔴")
        lines.append(f"{status_emoji} {p.get('project', '?')}: {p.get('status', '')} — {p.get('reason', '')}")
        lines.append(f"   active={p.get('active_count', 0)} pending={p.get('pending_count', 0)} rework={p.get('rework_signals', 0)} long_running={p.get('long_running', 0)}")
    return "\n".join(lines)


def format_priority_signals(data: dict[str, Any]) -> str:
    """Приоритетные сигналы: на что обратить внимание."""
    items = data.get("items") or []
    if not items:
        return "Приоритетных сигналов нет."
    lines = ["⚡ Priority signals:"]
    for s in items[:5]:
        lines.append(f"- [{s.get('priority', '')}] {s.get('reason', '')}")
        lines.append(f"  → {s.get('suggested_action', '')}")
    return "\n".join(lines)


def format_risk_signals(data: dict[str, Any]) -> str:
    """Риски: почему важно, что делать."""
    items = data.get("items") or []
    if not items:
        return "Явных рисков не обнаружено."
    lines = ["⚠️ Risks:"]
    for r in items[:5]:
        lines.append(f"- {r.get('risk_type', '')}: {r.get('reason', '')}")
        lines.append(f"  Почему важно: {r.get('why_it_matters', '')}")
        lines.append(f"  Действие: {r.get('suggested_action', '')}")
    return "\n".join(lines)


def format_strategic_weekly_digest(data: dict[str, Any]) -> str:
    """Стратегическая недельная сводка."""
    lines = [
        "🧭 Strategic weekly digest",
        f"Completed: {data.get('completed_count', 0)} | Pending approvals: {data.get('pending_approvals_count', 0)} | Blockers: {data.get('blockers_count', 0)}",
        f"Rework (7d): {data.get('rework_count', 0)} | Degraded signals: {data.get('degraded_events_count', 0)}",
        "",
        f"Owner focus: {data.get('owner_focus', '')}",
    ]
    risks = data.get("key_risks") or []
    if risks:
        lines.append("")
        lines.append("Key risks:")
        for r in risks[:3]:
            lines.append(f"- {r.get('reason', '')} → {r.get('suggested_action', '')}")
    needs = data.get("needs_decision") or []
    if needs:
        lines.append("")
        lines.append("Needs decision:")
        for n in needs[:3]:
            tid = n.get("task_id")
            lines.append(f"- Task #{tid}: {n.get('suggested_next_action', '')}" if tid else f"- {n.get('suggested_next_action', '')}")
    priorities = data.get("next_week_priorities") or []
    if priorities:
        lines.append("")
        lines.append("Next week priorities:")
        for p in priorities[:3]:
            lines.append(f"- {p.get('suggested_action', '')}")
    return "\n".join(lines)


def format_monthly_digest_baseline(data: dict[str, Any]) -> str:
    """Baseline месячной сводки (30 дней)."""
    lines = [
        "📅 Monthly digest (last 30 days)",
        f"Completed: {data.get('completed_count', 0)} | Active: {data.get('active_count', 0)}",
        f"Pending approvals: {data.get('pending_approvals_count', 0)} | Rework events: {data.get('rework_count', 0)}",
        f"Degraded incidents: {data.get('degraded_incidents_count', 0)}",
        "",
        "Top recommendations:",
    ]
    recs = data.get("top_recommendations") or []
    for r in recs[:3]:
        lines.append(f"- {r.get('suggested_action', '')} ({r.get('reason', '')})")
    if not recs:
        lines.append("- Нет срочных рекомендаций.")
    return "\n".join(lines)
