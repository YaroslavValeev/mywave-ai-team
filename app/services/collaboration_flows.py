# app/services/collaboration_flows.py — Phase 10.9: domain-aware collaboration and handoff
from __future__ import annotations

from collections import defaultdict
from typing import Any, List

from app.services.owner_insights import (
    get_awaiting_decisions_summary,
    get_blockers_summary,
    get_long_running_summary,
    get_rework_signal_summary,
    get_degraded_signal_summary,
)
from app.services.owner_queries import get_system_status_summary
from app.services.project_queries import list_projects, get_project_pending_approvals, get_project_risks


def get_task_handoff_signals(task_id: int) -> dict[str, Any]:
    """Handoff signals для одной задачи: кто держит, кому передать, готовность."""
    try:
        from app.storage.repositories import get_session_factory, TaskRepository
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            task = repo.get_task(task_id)
    except Exception:
        return {"task_id": task_id, "handoff_signals": [], "error": "task not found"}
    if not task:
        return {"task_id": task_id, "handoff_signals": [], "error": "task not found"}
    signals = []
    status = getattr(task, "status", "")
    if status in ("WAIT_OWNER", "APPROVED_WAIT_MERGE"):
        signals.append({
            "source_role": "executor",
            "target_role": "owner",
            "handoff_type": "executor_to_owner",
            "handoff_reason": "pending approval",
            "handoff_readiness": "ready",
            "handoff_blockers": [],
            "recommended_next_role": "owner",
            "collaboration_priority": "high",
        })
    elif status == "REWORK":
        signals.append({
            "source_role": "owner",
            "target_role": "executor",
            "handoff_type": "owner_to_executor",
            "handoff_reason": "rework",
            "handoff_readiness": "ready",
            "handoff_blockers": [],
            "recommended_next_role": "executor",
            "collaboration_priority": "medium",
        })
    status_summary = get_system_status_summary()
    if status_summary.get("state") == "DEGRADED":
        signals.append({
            "source_role": "operator",
            "target_role": "owner",
            "handoff_type": "operator_to_owner",
            "handoff_reason": "runtime degraded",
            "handoff_readiness": "ready",
            "handoff_blockers": [],
            "recommended_next_role": "owner",
            "collaboration_priority": "high",
        })
    return {
        "task_id": task_id,
        "task_status": status,
        "handoff_signals": signals,
        "project_key": (getattr(task, "domain", None) or getattr(task, "task_type", None) or "general"),
    }


def get_project_handoff_signals(project_key: str) -> dict[str, Any]:
    """Handoff signals по проекту: bottleneck, loop, attention gap."""
    pending = get_project_pending_approvals(project_key, limit=50)
    risks = get_project_risks(project_key, limit=20)
    items_pending = pending.get("items", [])
    count_pending = pending.get("count", len(items_pending))
    signals = []
    if count_pending >= 2:
        signals.append({
            "source_role": "executor",
            "target_role": "owner",
            "handoff_type": "executor_to_owner",
            "handoff_reason": "approval_bottleneck",
            "handoff_readiness": "blocked",
            "handoff_blockers": [f"{count_pending} задач ждут решения owner"],
            "recommended_next_role": "owner",
            "collaboration_priority": "high",
            "evidence_summary": f"{count_pending} pending approvals",
        })
    rework_risks = [r for r in risks.get("items", []) if r.get("risk_type") == "rework_accumulation"]
    if rework_risks:
        signals.append({
            "source_role": "owner",
            "target_role": "executor",
            "handoff_type": "review_execution_loop",
            "handoff_reason": "rework accumulation",
            "handoff_readiness": "partial",
            "handoff_blockers": [],
            "recommended_next_role": "owner",
            "collaboration_priority": "medium",
            "evidence_summary": "rework accumulation in project",
        })
    try:
        from app.services.project_domain_mapping import get_project_domain_profile
        profile = get_project_domain_profile(project_key)
        mismatch = profile.get("mismatch_signals") or []
        if mismatch and count_pending >= 1:
            signals.append({
                "source_role": "executor",
                "target_role": "owner",
                "handoff_type": "domain_handoff_mismatch",
                "handoff_reason": "override-heavy + pending",
                "handoff_readiness": "partial",
                "handoff_blockers": [],
                "recommended_next_role": "owner",
                "collaboration_priority": "low",
                "evidence_summary": "domain override-heavy with pending",
            })
    except Exception:
        pass
    return {
        "project_key": project_key,
        "handoff_signals": signals,
        "pending_count": count_pending,
        "risks_count": len(risks.get("items", [])),
    }


def get_role_collaboration_summary(role_key: str) -> dict[str, Any]:
    """Collaboration summary для роли: next targets, handoff pressure."""
    awaiting = get_awaiting_decisions_summary(limit=20)
    rework = get_rework_signal_summary(limit=10)
    blockers = get_blockers_summary(limit=10)
    long_running = get_long_running_summary(limit=10)
    status = get_system_status_summary()
    items = []
    if role_key == "owner":
        for t in awaiting.get("items", [])[:5]:
            items.append({
                "source_role": "executor",
                "target_role": "owner",
                "handoff_type": "executor_to_owner",
                "reason": "Pending approval",
                "task_id": getattr(t, "id", None),
                "urgency": "high",
            })
        if status.get("state") == "DEGRADED":
            items.append({
                "source_role": "operator",
                "target_role": "owner",
                "handoff_type": "operator_to_owner",
                "reason": "Runtime degraded",
                "task_id": None,
                "urgency": "high",
            })
    elif role_key == "reviewer":
        for t in awaiting.get("items", [])[:5]:
            items.append({
                "source_role": "executor",
                "target_role": "owner",
                "handoff_type": "executor_to_owner",
                "reason": "Items need owner decision",
                "task_id": getattr(t, "id", None),
                "urgency": "high",
            })
    elif role_key == "executor":
        for t in rework.get("items", [])[:5]:
            items.append({
                "source_role": "owner",
                "target_role": "executor",
                "handoff_type": "owner_to_executor",
                "reason": "Rework",
                "task_id": getattr(t, "id", None),
                "urgency": "medium",
            })
        for i in blockers.get("items", [])[:3]:
            t = i.get("task")
            if t:
                items.append({
                    "source_role": "operator",
                    "target_role": "executor",
                    "handoff_type": "blocker",
                    "reason": i.get("kind", "blocker"),
                    "task_id": getattr(t, "id", None),
                    "urgency": "medium",
                })
    elif role_key == "operator":
        if status.get("state") == "DEGRADED":
            items.append({
                "source_role": "operator",
                "target_role": "owner",
                "handoff_type": "operator_to_owner",
                "reason": "Runtime degraded — escalate to owner",
                "task_id": None,
                "urgency": "high",
            })
        for i in (blockers.get("items", []) + long_running.get("items", []))[:5]:
            t = i.get("task") if isinstance(i, dict) else i
            if t:
                items.append({
                    "source_role": "operator",
                    "target_role": "owner",
                    "handoff_type": "runtime_escalation",
                    "reason": "Blocker or long-running",
                    "task_id": getattr(t, "id", None),
                    "urgency": "medium",
                })
    return {
        "role_key": role_key,
        "collaboration_items": items[:10],
        "count": len(items[:10]),
    }


def get_cross_role_handoffs(window_days: int = 7, limit: int = 20) -> List[dict[str, Any]]:
    """Cross-role handoffs за окно (по текущему состоянию, без исторического окна)."""
    awaiting = get_awaiting_decisions_summary(limit=limit)
    rework = get_rework_signal_summary(limit=limit)
    status = get_system_status_summary()
    handoffs = []
    for t in awaiting.get("items", []):
        handoffs.append({
            "handoff_type": "executor_to_owner",
            "source_role": "executor",
            "target_role": "owner",
            "task_id": getattr(t, "id", None),
            "reason": "pending approval",
            "project_key": (getattr(t, "domain", None) or getattr(t, "task_type", None) or "general"),
        })
    for t in rework.get("items", []):
        handoffs.append({
            "handoff_type": "owner_to_executor",
            "source_role": "owner",
            "target_role": "executor",
            "task_id": getattr(t, "id", None),
            "reason": "rework",
            "project_key": (getattr(t, "domain", None) or getattr(t, "task_type", None) or "general"),
        })
    if status.get("state") == "DEGRADED":
        handoffs.append({
            "handoff_type": "operator_to_owner",
            "source_role": "operator",
            "target_role": "owner",
            "task_id": None,
            "reason": "runtime degraded",
            "project_key": None,
        })
    return handoffs[:limit]


def get_collaboration_hotspots(window_days: int = 7, limit: int = 15) -> List[dict[str, Any]]:
    """Collaboration hotspots: bottleneck, loop, escalation, attention gap."""
    hotspots = []
    awaiting = get_awaiting_decisions_summary(limit=50)
    rework = get_rework_signal_summary(limit=30)
    blockers = get_blockers_summary(limit=20)
    status = get_system_status_summary()
    projects = list_projects(limit=50)
    if awaiting.get("pending_count", 0) >= 2:
        hotspots.append({
            "hotspot_type": "approval_bottleneck",
            "roles_involved": ["executor", "owner"],
            "project_key": None,
            "domain_key": None,
            "reason": f"{awaiting.get('pending_count', 0)} задач ждут решения owner",
            "severity": "high",
            "evidence_summary": f"pending: {awaiting.get('pending_count', 0)}",
            "recommended_collaboration_action": "Разобрать approvals",
        })
    if rework.get("count", 0) >= 2:
        hotspots.append({
            "hotspot_type": "review_execution_loop",
            "roles_involved": ["owner", "executor"],
            "project_key": None,
            "domain_key": None,
            "reason": f"Повторный rework: {rework.get('count', 0)} задач",
            "severity": "medium",
            "evidence_summary": f"rework: {rework.get('count', 0)}",
            "recommended_collaboration_action": "Координировать owner–executor",
        })
    if status.get("state") == "DEGRADED" or (blockers.get("blockers_count") or 0) >= 2:
        hotspots.append({
            "hotspot_type": "runtime_escalation_gap",
            "roles_involved": ["operator", "owner"],
            "project_key": None,
            "domain_key": None,
            "reason": "Runtime degraded или блокеры требуют эскалации",
            "severity": "high",
            "evidence_summary": f"degraded={status.get('state') == 'DEGRADED'}, blockers={blockers.get('blockers_count', 0)}",
            "recommended_collaboration_action": "Operator → owner escalation",
        })
    for p in projects.get("items", []):
        pk = p.get("project_key")
        if not pk:
            continue
        pending_p = p.get("pending_count", 0)
        rework_p = p.get("rework_signals", 0)
        lr_p = p.get("long_running", 0)
        if (pending_p >= 1 and rework_p >= 1) or (pending_p >= 1 and lr_p >= 1):
            hotspots.append({
                "hotspot_type": "owner_attention_gap",
                "roles_involved": ["owner"],
                "project_key": pk,
                "domain_key": None,
                "reason": f"Проект {pk}: pending + rework/long-running",
                "severity": "medium",
                "evidence_summary": f"pending {pending_p}, rework {rework_p}, lr {lr_p}",
                "recommended_collaboration_action": "Выделить внимание owner по проекту",
            })
    try:
        instab = __import__("app.services.project_domain_lifecycle", fromlist=["get_project_domain_instability_signals"]).get_project_domain_instability_signals(window_days=30, limit=5)
        for lc in instab:
            pk = lc.get("project_key")
            if pk and awaiting.get("pending_count", 0) >= 1:
                hotspots.append({
                    "hotspot_type": "domain_handoff_mismatch",
                    "roles_involved": ["owner"],
                    "project_key": pk,
                    "domain_key": lc.get("current_dominant_domain"),
                    "reason": f"Нестабильный домен в проекте {pk} + pending",
                    "severity": "low",
                    "evidence_summary": lc.get("reason", ""),
                    "recommended_collaboration_action": "Проверить доменный профиль проекта",
                })
    except Exception:
        pass
    return hotspots[:limit]


def get_collaboration_recommendations(window_days: int = 7, limit: int = 15) -> List[dict[str, Any]]:
    """Recommendations для collaboration: кто что должен сделать."""
    recs = []
    awaiting = get_awaiting_decisions_summary(limit=20)
    for t in awaiting.get("items", [])[:5]:
        recs.append({
            "source_role": "executor",
            "target_role": "owner",
            "project_key": (getattr(t, "domain", None) or getattr(t, "task_type", None) or "general"),
            "domain_key": getattr(t, "domain", None),
            "reason": "Pending approval",
            "recommended_action": "Принять решение: approve / rework / clarify",
            "urgency": "high",
            "evidence_summary": f"task {getattr(t, 'id', '?')}",
        })
    rework = get_rework_signal_summary(limit=10)
    for t in rework.get("items", [])[:3]:
        recs.append({
            "source_role": "owner",
            "target_role": "executor",
            "project_key": (getattr(t, "domain", None) or getattr(t, "task_type", None) or "general"),
            "domain_key": getattr(t, "domain", None),
            "reason": "Rework",
            "recommended_action": "Executor доработать по rework",
            "urgency": "medium",
            "evidence_summary": f"task {getattr(t, 'id', '?')}, cycles={getattr(t, 'rework_cycles', 0)}",
        })
    status = get_system_status_summary()
    if status.get("state") == "DEGRADED":
        recs.append({
            "source_role": "operator",
            "target_role": "owner",
            "project_key": None,
            "domain_key": None,
            "reason": "Runtime degraded",
            "recommended_action": "Проверить Molt / runtime",
            "urgency": "high",
            "evidence_summary": "system state DEGRADED",
        })
    return recs[:limit]
