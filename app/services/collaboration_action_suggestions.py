# app/services/collaboration_action_suggestions.py — Phase 11.1: action suggestions and decision support
from __future__ import annotations

import hashlib
import uuid
from typing import Any, List, Optional

from app.services.collaboration_flows import (
    get_task_handoff_signals,
    get_project_handoff_signals,
    get_collaboration_hotspots,
    get_collaboration_recommendations,
    get_role_collaboration_summary,
)
from app.services.owner_insights import (
    get_awaiting_decisions_summary,
    get_blockers_summary,
    get_long_running_summary,
    get_rework_signal_summary,
    get_degraded_signal_summary,
)
from app.services.owner_queries import get_system_status_summary
from app.services.owner_portfolio import get_portfolio_focus_list


def compute_suggestion_fingerprint(s: dict[str, Any]) -> str:
    """Стабильный ключ для связи suggestion ↔ collaboration execution (Phase 11.4)."""
    key = "|".join([
        str(s.get("suggestion_type") or ""),
        str(s.get("subject_type") or ""),
        str(s.get("subject_key") or ""),
        (s.get("headline") or "")[:120],
    ])
    return "sf_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _enrich_suggestion(d: dict[str, Any]) -> dict[str, Any]:
    """Добавляет fingerprint, execution_exists, executable, pending_executions_for_subject."""
    fp = d.get("suggestion_fingerprint") or compute_suggestion_fingerprint(d)
    out = dict(d)
    out["suggestion_fingerprint"] = fp
    try:
        from app.services.collaboration_execution_store import find_open_by_fingerprint, count_pending_for_subject

        open_e = find_open_by_fingerprint(fp)
        out["execution_exists"] = open_e is not None
        out["execution_id"] = (open_e or {}).get("execution_id")
        out["executable"] = bool(out.get("safe_action_available"))
        out["pending_executions_for_subject"] = count_pending_for_subject(
            out.get("subject_type"), out.get("subject_key")
        )
    except Exception:
        out["execution_exists"] = False
        out["execution_id"] = None
        out["executable"] = bool(out.get("safe_action_available"))
        out["pending_executions_for_subject"] = 0
    return out


def _suggestion(
    suggestion_type: str,
    subject_type: str,
    subject_key: str,
    source_role: str,
    target_role: str,
    headline: str,
    reason: str,
    evidence_summary: List[str],
    recommended_next_step: str,
    urgency: str = "medium",
    confidence_label: str = "high",
    safe_action_available: Optional[str] = None,
    related_objects: Optional[List[dict]] = None,
) -> dict[str, Any]:
    d = {
        "suggestion_id": str(uuid.uuid4())[:8],
        "suggestion_type": suggestion_type,
        "subject_type": subject_type,
        "subject_key": subject_key,
        "source_role": source_role,
        "target_role": target_role,
        "headline": headline,
        "reason": reason,
        "evidence_summary": evidence_summary[:5],
        "recommended_next_step": recommended_next_step,
        "urgency": urgency,
        "confidence_label": confidence_label,
        "safe_action_available": safe_action_available,
        "related_objects": related_objects or [],
    }
    d["suggestion_fingerprint"] = compute_suggestion_fingerprint(d)
    return _enrich_suggestion(d)


def get_task_action_suggestions(task_id: int, limit: int = 5) -> dict[str, Any]:
    """Action suggestions по задаче (handoff, approval, rework)."""
    suggestions: List[dict] = []
    try:
        handoff = get_task_handoff_signals(task_id)
        sigs = handoff.get("handoff_signals", [])
        project_key = handoff.get("project_key", "general")
        for s in sigs[:limit]:
            target = s.get("recommended_next_role", "owner")
            step = f"/task {task_id} → approve/rework/clarify" if target == "owner" else f"/task {task_id} — rework"
            suggestions.append(_suggestion(
                "handoff_followup",
                "task",
                str(task_id),
                s.get("source_role", "executor"),
                target,
                f"Handoff: {s.get('handoff_type', '')} — {target}",
                s.get("handoff_reason", "handoff pending"),
                [s.get("handoff_reason", "")],
                step,
                urgency="high" if s.get("collaboration_priority") == "high" else "medium",
                related_objects=[{"task_id": task_id}],
            ))
        if not sigs:
            suggestions.append(_suggestion(
                "handoff_followup",
                "task",
                str(task_id),
                "system",
                "owner",
                "Task #%s — нет активных handoff" % task_id,
                "Задача в процессе или ожидает",
                [],
                f"/task {task_id} — проверить статус",
                urgency="low",
                related_objects=[{"task_id": task_id}],
            ))
    except Exception:
        pass
    return {"task_id": task_id, "suggestions": suggestions[:limit], "count": len(suggestions[:limit])}


def get_project_action_suggestions(project_key: str, window_days: int = 7, limit: int = 5) -> dict[str, Any]:
    """Action suggestions по проекту (bottleneck, lifecycle, collaboration)."""
    suggestions: List[dict] = []
    try:
        handoff = get_project_handoff_signals(project_key)
        sigs = handoff.get("handoff_signals", [])
        for s in sigs[:limit]:
            target = s.get("recommended_next_role", "owner")
            step = s.get("handoff_reason", "").replace("approval_bottleneck", "Разобрать approvals: /approvals")
            if "approval" in (s.get("handoff_type") or "").lower():
                step = "Разобрать approvals: /approvals или /owner/project/%s" % project_key
            elif "rework" in (s.get("handoff_reason") or "").lower():
                step = "Координировать owner–executor, уточнить постановку"
            suggestions.append(_suggestion(
                "approval_resolution_needed" if "approval" in (s.get("handoff_type") or "") else "rework_loop_break",
                "project",
                project_key,
                s.get("source_role", "executor"),
                target,
                f"Проект {project_key}: {s.get('handoff_reason', '')}",
                s.get("handoff_reason", ""),
                s.get("handoff_blockers", []) or [s.get("evidence_summary", "")],
                step,
                urgency="high" if s.get("collaboration_priority") == "high" else "medium",
                safe_action_available="open_decision_queue" if target == "owner" else None,
                related_objects=[{"project_key": project_key}],
            ))
        try:
            from app.services.project_domain_lifecycle import get_project_domain_lifecycle
            lc = get_project_domain_lifecycle(project_key, window_days=window_days)
            if lc.get("domain_drift_signal") or lc.get("domain_instability_signal"):
                suggestions.append(_suggestion(
                    "project_focus_intervention",
                    "project",
                    project_key,
                    "system",
                    "owner",
                    f"Проект {project_key}: дрифт/нестабильность домена",
                    lc.get("reason", "Domain drift or instability"),
                    [f"State: {lc.get('lifecycle_state', '')}", f"Домен: {lc.get('current_dominant_domain', '')}"],
                    "/owner/project/%s или /domain_lifecycle" % project_key,
                    urgency="low",
                    related_objects=[{"project_key": project_key}],
                ))
        except Exception:
            pass
    except Exception:
        pass
    return {"project_key": project_key, "suggestions": suggestions[:limit], "count": len(suggestions[:limit])}


def get_portfolio_action_suggestions(window_days: int = 7, limit: int = 10) -> dict[str, Any]:
    """Action suggestions по портфелю (focus list, hotspots)."""
    suggestions: List[dict] = []
    try:
        focus = get_portfolio_focus_list(limit=limit)
        items = focus.get("items", [])
        for p in items[:5]:
            pk = p.get("project_key", "")
            reason = p.get("reason", "")
            action = p.get("suggested_action", "Проверить проект")
            suggestions.append(_suggestion(
                "project_focus_intervention",
                "portfolio",
                pk or "portfolio",
                "system",
                "owner",
                f"Focus: {pk} — {reason[:50]}",
                reason,
                [action],
                "/owner/project/%s" % pk if pk else "/owner/portfolio",
                urgency="high" if p.get("status") == "critical" else "medium",
                related_objects=[{"project_key": pk}],
            ))
        hotspots = get_collaboration_hotspots(window_days=window_days, limit=5)
        for h in hotspots[:3]:
            suggestions.append(_suggestion(
                "owner_attention_request",
                "portfolio",
                "portfolio",
                "system",
                "owner",
                h.get("reason", "Collaboration hotspot")[:60],
                h.get("recommended_collaboration_action", ""),
                [h.get("evidence_summary", "")],
                h.get("recommended_collaboration_action", "Разобрать /owner/collaboration"),
                urgency="high" if h.get("severity") == "high" else "medium",
                safe_action_available="open_decision_queue",
                related_objects=[],
            ))
    except Exception:
        pass
    return {"suggestions": suggestions[:limit], "count": len(suggestions[:limit]), "window_days": window_days}


def get_role_action_suggestions(role_key: str, window_days: int = 7, limit: int = 5) -> dict[str, Any]:
    """Action suggestions для роли (collaboration items)."""
    suggestions: List[dict] = []
    try:
        collab = get_role_collaboration_summary(role_key)
        items = collab.get("collaboration_items", [])
        for i in items[:limit]:
            task_id = i.get("task_id")
            pk = "task" if task_id else "general"
            step = f"/task {task_id}" if task_id else "/owner"
            if i.get("handoff_type") == "executor_to_owner":
                step = "/approvals или /owner"
            elif i.get("handoff_type") == "owner_to_executor":
                step = f"/task {task_id} — rework" if task_id else "Rework tasks"
            suggestions.append(_suggestion(
                "handoff_followup" if task_id else "owner_attention_request",
                "task" if task_id else "portfolio",
                str(task_id) if task_id else "portfolio",
                i.get("source_role", "system"),
                i.get("target_role", "owner"),
                i.get("reason", "Collaboration item")[:60],
                i.get("reason", ""),
                [],
                step,
                urgency=i.get("urgency", "medium"),
                related_objects=[{"task_id": task_id}] if task_id else [],
            ))
    except Exception:
        pass
    return {"role_key": role_key, "suggestions": suggestions[:limit], "count": len(suggestions[:limit])}


def get_collaboration_action_suggestions(window_days: int = 7, limit: int = 10) -> dict[str, Any]:
    """Action suggestions по collaboration (hotspots, recommendations)."""
    suggestions: List[dict] = []
    try:
        hotspots = get_collaboration_hotspots(window_days=window_days, limit=limit)
        for h in hotspots[:5]:
            suggestions.append(_suggestion(
                "approval_resolution_needed" if h.get("hotspot_type") == "approval_bottleneck" else "owner_attention_request",
                "collaboration_hotspot",
                h.get("project_key") or "portfolio",
                "system",
                "owner",
                h.get("reason", "")[:60],
                h.get("reason", ""),
                [h.get("recommended_collaboration_action", ""), h.get("evidence_summary", "")],
                h.get("recommended_collaboration_action", "/owner/collaboration"),
                urgency="high" if h.get("severity") == "high" else "medium",
                safe_action_available="open_decision_queue",
                related_objects=[{"project_key": h.get("project_key")}] if h.get("project_key") else [],
            ))
        status = get_system_status_summary()
        if status.get("state") == "DEGRADED":
            suggestions.append(_suggestion(
                "runtime_escalation",
                "portfolio",
                "portfolio",
                "operator",
                "owner",
                "Runtime degraded — эскалация owner",
                "Runtime degraded",
                ["Molt/boundary check needed"],
                "Проверить Molt, /recheck_molt_health",
                urgency="high",
                safe_action_available="recheck_molt_health",
                related_objects=[],
            ))
    except Exception:
        pass
    return {"suggestions": suggestions[:limit], "count": len(suggestions[:limit]), "window_days": window_days}


def get_decision_support(
    scope_type: str,
    scope_key: Optional[str] = None,
    window_days: int = 7,
    limit: int = 5,
) -> dict[str, Any]:
    """Decision support block: options, preferred, risk_if_ignored."""
    items: List[dict] = []
    try:
        if scope_type == "task" and scope_key:
            tid = int(scope_key)
            sug = get_task_action_suggestions(tid, limit=limit)
            for s in sug.get("suggestions", []):
                items.append({
                    "decision_support_id": str(uuid.uuid4())[:8],
                    "decision_type": "approval_pending" if "approval" in (s.get("recommended_next_step") or "") else "collaboration_bottleneck",
                    "scope_type": "task",
                    "scope_key": scope_key,
                    "headline": s.get("headline", ""),
                    "why_now": s.get("reason", ""),
                    "options": [{"label": "Выполнить", "description": s.get("recommended_next_step", ""), "action_hint": s.get("safe_action_available") or s.get("recommended_next_step", "")}],
                    "preferred_option": "Выполнить",
                    "preferred_option_reason": s.get("reason", ""),
                    "risk_if_ignored": "Handoff останется открытым",
                    "evidence_items": s.get("evidence_summary", []),
                    "related_suggestions": [s.get("suggestion_id", "")],
                })
        elif scope_type == "project" and scope_key:
            sug = get_project_action_suggestions(scope_key, window_days=window_days, limit=limit)
            for s in sug.get("suggestions", []):
                items.append({
                    "decision_support_id": str(uuid.uuid4())[:8],
                    "decision_type": "project_intervention",
                    "scope_type": "project",
                    "scope_key": scope_key,
                    "headline": s.get("headline", ""),
                    "why_now": s.get("reason", ""),
                    "options": [{"label": "Действовать", "description": s.get("recommended_next_step", ""), "action_hint": s.get("safe_action_available") or s.get("recommended_next_step", "")}],
                    "preferred_option": "Действовать",
                    "preferred_option_reason": s.get("reason", ""),
                    "risk_if_ignored": "Проект может застрять",
                    "evidence_items": s.get("evidence_summary", []),
                    "related_suggestions": [s.get("suggestion_id", "")],
                })
        elif scope_type == "portfolio":
            sug = get_portfolio_action_suggestions(window_days=window_days, limit=limit)
            for s in sug.get("suggestions", [])[:3]:
                items.append({
                    "decision_support_id": str(uuid.uuid4())[:8],
                    "decision_type": "portfolio_priority",
                    "scope_type": "portfolio",
                    "scope_key": scope_key or "",
                    "headline": s.get("headline", ""),
                    "why_now": s.get("reason", ""),
                    "options": [{"label": "Приоритет", "description": s.get("recommended_next_step", ""), "action_hint": s.get("safe_action_available") or s.get("recommended_next_step", "")}],
                    "preferred_option": "Приоритет",
                    "preferred_option_reason": s.get("reason", ""),
                    "risk_if_ignored": "Внимание рассеивается",
                    "evidence_items": s.get("evidence_summary", []),
                    "related_suggestions": [s.get("suggestion_id", "")],
                })
        else:
            sug = get_collaboration_action_suggestions(window_days=window_days, limit=limit)
            for s in sug.get("suggestions", [])[:3]:
                items.append({
                    "decision_support_id": str(uuid.uuid4())[:8],
                    "decision_type": "collaboration_bottleneck",
                    "scope_type": "collaboration_hotspot",
                    "scope_key": scope_key or "",
                    "headline": s.get("headline", ""),
                    "why_now": s.get("reason", ""),
                    "options": [{"label": "Разобрать", "description": s.get("recommended_next_step", ""), "action_hint": s.get("safe_action_available") or s.get("recommended_next_step", "")}],
                    "preferred_option": "Разобрать",
                    "preferred_option_reason": s.get("reason", ""),
                    "risk_if_ignored": "Bottleneck сохранится",
                    "evidence_items": s.get("evidence_summary", []),
                    "related_suggestions": [s.get("suggestion_id", "")],
                })
    except Exception:
        pass
    return {
        "scope_type": scope_type,
        "scope_key": scope_key,
        "items": items[:limit],
        "count": len(items[:limit]),
        "window_days": window_days,
    }
