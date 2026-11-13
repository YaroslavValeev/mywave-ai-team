# app/services/domain_specialization_analytics.py — Phase 10.5: override and specialization analytics
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.storage.repositories import get_session_factory, TaskRepository
from app.storage.models import AuditEvent

OVERRIDE_EVENTS = ("domain_override", "domain_override_cleared")
SPEC_EVENTS = ("specialization_selected", "specialization_fallback_used")
HOTSPOT_MIN_COUNT = 2


def _since(window_days: int):
    return datetime.now(timezone.utc) - timedelta(days=window_days)


def _project_key_from_task(task: Any) -> str:
    k = (getattr(task, "domain", None) or getattr(task, "task_type", None) or "general")
    return (k or "general").strip() or "general"


def get_domain_override_summary(window_days: int = 30) -> dict[str, Any]:
    """Сводка по domain override за окно: total_overrides, total_cleared, unique_tasks, override_rate."""
    Session = get_session_factory()
    with Session() as session:
        since_ts = _since(window_days)
        overrides = session.query(AuditEvent).filter(
            AuditEvent.event_type == "domain_override",
            AuditEvent.created_at >= since_ts,
        ).all()
        cleared = session.query(AuditEvent).filter(
            AuditEvent.event_type == "domain_override_cleared",
            AuditEvent.created_at >= since_ts,
        ).all()
    task_ids = list({e.task_id for e in overrides if e.task_id})
    denom = max(1, len(task_ids))
    return {
        "total_overrides": len(overrides),
        "total_cleared": len(cleared),
        "unique_tasks_with_override": len(task_ids),
        "window_days": window_days,
        "override_rate": round(len(overrides) / denom, 2),
        "explainable": True,
    }


def get_override_hotspots(window_days: int = 30, limit: int = 15) -> list[dict[str, Any]]:
    """Override hotspots: по domain и по project (count >= HOTSPOT_MIN_COUNT)."""
    Session = get_session_factory()
    with Session() as session:
        since_ts = _since(window_days)
        overrides = session.query(AuditEvent).filter(
            AuditEvent.event_type == "domain_override",
            AuditEvent.created_at >= since_ts,
        ).all()
    by_domain: dict[str, list[int]] = defaultdict(list)
    task_id_to_domain: dict[int, str] = {}
    for e in overrides:
        if not e.task_id:
            continue
        payload = e.payload_json or {}
        domain_key = (payload.get("new_primary_domain") or "other").strip() or "other"
        by_domain[domain_key].append(e.task_id)
        task_id_to_domain[e.task_id] = domain_key
    task_ids = list(set(tid for ids in by_domain.values() for tid in ids))
    by_project: dict[str, list[int]] = defaultdict(list)
    if task_ids:
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            for tid in task_ids[:500]:
                t = repo.get_task(tid)
                if t:
                    pk = _project_key_from_task(t)
                    by_project[pk].append(tid)
    hotspots = []
    for domain_key, ids in sorted(by_domain.items(), key=lambda x: -len(x[1])):
        if len(ids) >= HOTSPOT_MIN_COUNT:
            hotspots.append({
                "type": "domain",
                "key": domain_key,
                "count": len(ids),
                "reason_summary": f"{len(ids)} overrides to domain {domain_key} in window",
            })
    for project_key, ids in sorted(by_project.items(), key=lambda x: -len(x[1])):
        if len(ids) >= HOTSPOT_MIN_COUNT:
            hotspots.append({
                "type": "project",
                "key": project_key,
                "count": len(ids),
                "reason_summary": f"{len(ids)} overrides in project {project_key}",
            })
    return hotspots[:limit]


def get_specialization_fallback_summary(window_days: int = 30) -> dict[str, Any]:
    """Сводка по specialization: fallback vs selected за окно."""
    Session = get_session_factory()
    with Session() as session:
        since_ts = _since(window_days)
        fallback = session.query(AuditEvent).filter(
            AuditEvent.event_type == "specialization_fallback_used",
            AuditEvent.created_at >= since_ts,
        ).all()
        selected = session.query(AuditEvent).filter(
            AuditEvent.event_type == "specialization_selected",
            AuditEvent.created_at >= since_ts,
        ).all()
    total_f = len(fallback)
    total_s = len(selected)
    total = total_f + total_s or 1
    task_ids_f = list({e.task_id for e in fallback if e.task_id})
    return {
        "total_fallback_events": total_f,
        "total_selected_events": total_s,
        "fallback_rate": round(total_f / total, 2),
        "unique_tasks_with_fallback": len(task_ids_f),
        "window_days": window_days,
        "explainable": True,
    }


def get_specialization_hotspots(window_days: int = 30, limit: int = 15) -> list[dict[str, Any]]:
    """Hotspots по (domain, step) с высоким числом fallback."""
    Session = get_session_factory()
    with Session() as session:
        since_ts = _since(window_days)
        fallback = session.query(AuditEvent).filter(
            AuditEvent.event_type == "specialization_fallback_used",
            AuditEvent.created_at >= since_ts,
        ).all()
    by_key: dict[tuple[str, str], list[str]] = defaultdict(list)
    for e in fallback:
        p = e.payload_json or {}
        domain_key = (p.get("effective_domain") or "general").strip() or "general"
        step = (p.get("workflow_step") or "pipeline").strip() or "pipeline"
        reason = (p.get("reason") or "")[:80]
        by_key[(domain_key, step)].append(reason or "fallback")
    hotspots = []
    for (domain_key, workflow_step), reasons in sorted(by_key.items(), key=lambda x: -len(x[1])):
        if len(reasons) >= HOTSPOT_MIN_COUNT:
            hotspots.append({
                "domain_key": domain_key,
                "workflow_step": workflow_step,
                "fallback_count": len(reasons),
                "reason_summary": reasons[0] if reasons else "fallback",
            })
    return hotspots[:limit]


def get_refinement_signals(window_days: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Explainable refinement signals из эвристик (override-heavy, fallback hotspot)."""
    signals = []
    override_summary = get_domain_override_summary(window_days)
    override_hotspots = get_override_hotspots(window_days, limit=10)
    spec_summary = get_specialization_fallback_summary(window_days)
    spec_hotspots = get_specialization_hotspots(window_days, limit=10)

    for h in override_hotspots:
        if h.get("type") == "domain":
            signals.append({
                "signal_type": "override_heavy_domain",
                "severity": "medium" if h.get("count", 0) >= 3 else "low",
                "reason": f"Частые override на домен {h.get('key')} ({h.get('count')} за период)",
                "recommended_refinement_action": f"Проверить routing/keywords для домена {h.get('key')}",
                "evidence_summary": h.get("reason_summary", ""),
                "domain_key": h.get("key"),
            })
        elif h.get("type") == "project":
            signals.append({
                "signal_type": "override_heavy_project",
                "severity": "medium" if h.get("count", 0) >= 3 else "low",
                "reason": f"Много override в проекте {h.get('key')} ({h.get('count')})",
                "recommended_refinement_action": "Просмотреть причины override по задачам проекта",
                "evidence_summary": h.get("reason_summary", ""),
                "project_key": h.get("key"),
            })
    for h in spec_hotspots:
        signals.append({
            "signal_type": "frequent_fallback_domain_step",
            "severity": "medium" if (h.get("fallback_count") or 0) >= 3 else "low",
            "reason": f"Частый fallback: домен {h.get('domain_key')}, шаг {h.get('workflow_step')} ({h.get('fallback_count')})",
            "recommended_refinement_action": f"Добавить/расширить профиль специализации для {h.get('domain_key')}, {h.get('workflow_step')}",
            "evidence_summary": h.get("reason_summary", ""),
            "domain_key": h.get("domain_key"),
            "workflow_step": h.get("workflow_step"),
        })
    if spec_summary.get("fallback_rate", 0) >= 0.4 and spec_summary.get("total_fallback_events", 0) >= 2:
        signals.append({
            "signal_type": "unstable_execution_lane",
            "severity": "low",
            "reason": f"Высокий fallback rate ({spec_summary.get('fallback_rate')}) по специализациям",
            "recommended_refinement_action": "Расширить реестр специализаций или проверить домены задач",
            "evidence_summary": f"fallback_events={spec_summary.get('total_fallback_events')}, rate={spec_summary.get('fallback_rate')}",
        })
    return signals[:limit]


def get_refinement_backlog(window_days: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Backlog actionable items из refinement signals (refinement_item_key, recommended_change)."""
    signals = get_refinement_signals(window_days, limit=limit * 2)
    backlog = []
    for s in signals:
        st = s.get("signal_type", "")
        dk = s.get("domain_key", "")
        wk = s.get("workflow_step", "")
        pk = s.get("project_key", "")
        key = f"{st}:{dk or pk}:{wk}".strip(":")
        action = s.get("recommended_refinement_action", "")
        if "профиль" in action.lower() or "specialization" in action.lower() or "profile" in action.lower():
            recommended_change = "add/expand specialization profile"
        elif "routing" in action.lower() or "keywords" in action.lower():
            recommended_change = "improve routing keywords"
        elif "override" in action.lower() or "причины" in action.lower():
            recommended_change = "inspect override reasons manually"
        else:
            recommended_change = "review alias map"
        backlog.append({
            "refinement_item_key": key,
            "item_type": st,
            "domain_key": dk or None,
            "workflow_step": wk or None,
            "project_key": pk or None,
            "severity": s.get("severity", "low"),
            "reason": s.get("reason", ""),
            "recommended_change": recommended_change,
            "evidence_summary": s.get("evidence_summary", ""),
            "window_days": window_days,
        })
    return backlog[:limit]
