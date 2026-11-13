# app/services/explanation_assist.py — Phase 11.0: unified explanation and rationale
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rationale(
    rationale_type: str,
    subject_type: str,
    subject_key: str,
    headline: str,
    summary: str = "",
    reason: str = "",
    evidence_items: List[str] | None = None,
    signals_used: List[str] | None = None,
    confidence_label: str = "medium",
    recommended_action: Optional[str] = None,
    related_objects: List[dict] | None = None,
) -> dict[str, Any]:
    return {
        "rationale_type": rationale_type,
        "subject_type": subject_type,
        "subject_key": subject_key,
        "headline": headline,
        "summary": summary or headline,
        "reason": reason or headline,
        "evidence_items": (evidence_items or [])[:5],
        "signals_used": signals_used or [],
        "confidence_label": confidence_label,
        "recommended_action": recommended_action,
        "related_objects": related_objects or [],
        "generated_at": _utc_now(),
    }


def explain_task(task_id: int) -> dict[str, Any]:
    """Объяснение по задаче: domain, specialization, override, handoff."""
    rationales: List[dict] = []
    project_key = "general"
    try:
        from app.storage.repositories import get_session_factory, TaskRepository
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            task = repo.get_task(task_id)
        if not task:
            return {"task_id": task_id, "rationales": [], "error": "task not found"}
        project_key = (getattr(task, "domain", None) or getattr(task, "task_type", None) or "general")
        task_text = getattr(task, "owner_text", None) or ""

        # Domain rationale
        try:
            from app.services.workflow_domain_context import get_effective_domain_context
            eff = get_effective_domain_context(task_id, task_text)
            primary = eff.get("selected_primary_domain") or "general"
            source = eff.get("context_selection_source", "auto")
            reason = eff.get("context_selection_reason", "")
            override = eff.get("domain_override", False)
            ev = [f"Домен: {primary}", f"Source: {source}"]
            if override:
                ev.append("Override: да")
            else:
                ev.append("Override: нет")
            if reason:
                ev.append(reason[:80])
            headline = f"Домен: {primary} — {'override' if override else source}"
            rationales.append(_rationale(
                "domain_selection_rationale",
                "task",
                str(task_id),
                headline,
                reason or f"Выбор домена {primary} по контексту задачи.",
                reason,
                ev[:5],
                ["workflow_domain_context", "domain_triage"],
                "high" if not override else "high",
                None,
                [{"task_id": task_id}],
            ))
        except Exception:
            pass

        # Specialization rationale
        try:
            from app.services.agent_specializations import suggest_specialization
            sel = suggest_specialization(task_id, "pipeline", task_text)
            spec = (sel.get("selected_specialization") or {}).get("specialization_key", "general_pipeline")
            spec_reason = sel.get("selection_reason", "")
            fallback = sel.get("fallback_used", False)
            ev = [f"Specialization: {spec}", f"Fallback: {'да' if fallback else 'нет'}"]
            if spec_reason:
                ev.append(spec_reason[:60])
            rationales.append(_rationale(
                "specialization_rationale",
                "task",
                str(task_id),
                f"Specialization: {spec}" + (" (fallback)" if fallback else ""),
                spec_reason or f"Профиль {spec} по домену и шагу pipeline.",
                spec_reason,
                ev[:5],
                ["agent_specializations"],
                "high" if not fallback else "medium",
                None,
                [{"task_id": task_id}],
            ))
        except Exception:
            pass

        # Handoff/collaboration rationale
        try:
            from app.services.collaboration_flows import get_task_handoff_signals
            handoff = get_task_handoff_signals(task_id)
            sigs = handoff.get("handoff_signals", [])
            if sigs:
                h = sigs[0]
                ht = h.get("handoff_type", "")
                reason = h.get("handoff_reason", "")
                target = h.get("recommended_next_role", "")
                rationales.append(_rationale(
                    "collaboration_rationale",
                    "task",
                    str(task_id),
                    f"Handoff: {ht} — следующий: {target}",
                    reason,
                    reason,
                    [f"Type: {ht}", f"Target: {target}", f"Reason: {reason}"][:5],
                    ["collaboration_flows"],
                    "high",
                    f"Разобрать: /approvals или /task {task_id}" if target == "owner" else None,
                    [{"task_id": task_id}],
                ))
        except Exception:
            pass
    except Exception as e:
        return {"task_id": task_id, "rationales": [], "error": str(e)}

    return {"task_id": task_id, "project_key": project_key, "rationales": rationales}


def explain_project(project_key: str, window_days: int = 30) -> dict[str, Any]:
    """Объяснение по проекту: dominant domain, lifecycle, collaboration."""
    rationales: List[dict] = []
    try:
        # Lifecycle
        try:
            from app.services.project_domain_lifecycle import get_project_domain_lifecycle
            lc = get_project_domain_lifecycle(project_key, window_days=window_days)
            state = lc.get("lifecycle_state", "")
            curr = lc.get("current_dominant_domain", "")
            reason = lc.get("reason", "")
            drift = lc.get("domain_drift_signal", False)
            instab = lc.get("domain_instability_signal", False)
            ev = [f"State: {state}", f"Домен: {curr}"]
            if drift:
                ev.append("Drift: да")
            if instab:
                ev.append("Нестабильность: да")
            headline = f"Проект {project_key}: {state}, домен {curr}"
            rationales.append(_rationale(
                "lifecycle_rationale",
                "project",
                project_key,
                headline,
                reason,
                reason,
                ev[:5],
                ["project_domain_lifecycle"],
                "high" if state != "weak_signal" else "low",
                "Проверить /owner/project/" + project_key if (drift or instab) else None,
                [{"project_key": project_key}],
            ))
        except Exception:
            pass

        # Project domain profile
        try:
            from app.services.project_domain_mapping import get_project_domain_profile
            profile = get_project_domain_profile(project_key)
            dom = profile.get("dominant_domain", "")
            mismatch = profile.get("mismatch_signals") or []
            ev = [f"Dominant: {dom}"]
            for m in mismatch[:2]:
                ev.append((m.get("reason") or m.get("type", ""))[:50])
            if ev:
                rationales.append(_rationale(
                    "domain_selection_rationale",
                    "project",
                    project_key,
                    f"Доминанта: {dom}" + (" (mismatch)" if mismatch else ""),
                    "; ".join((m.get("reason", "") or m.get("type", ""))[:40] for m in mismatch[:2]) if mismatch else f"Домен {dom} по задачам проекта.",
                    "",
                    ev[:5],
                    ["project_domain_mapping"],
                    "high" if not mismatch else "medium",
                    None,
                    [{"project_key": project_key}],
                ))
        except Exception:
            pass

        # Collaboration
        try:
            from app.services.collaboration_flows import get_project_handoff_signals
            ph = get_project_handoff_signals(project_key)
            sigs = ph.get("handoff_signals", [])
            if sigs:
                h = sigs[0]
                rationales.append(_rationale(
                    "collaboration_rationale",
                    "project",
                    project_key,
                    f"Handoff: {h.get('handoff_type', '')} — {h.get('handoff_reason', '')}",
                    h.get("evidence_summary", h.get("handoff_reason", "")),
                    h.get("handoff_reason", ""),
                    [f"Pending: {ph.get('pending_count', 0)}", h.get("handoff_reason", "")][:5],
                    ["collaboration_flows"],
                    "high",
                    h.get("recommended_next_role") and f"Передать {h.get('recommended_next_role')}",
                    [{"project_key": project_key}],
                ))
        except Exception:
            pass
    except Exception as e:
        return {"project_key": project_key, "rationales": [], "error": str(e)}

    return {"project_key": project_key, "rationales": rationales}


def explain_portfolio(window_days: int = 7) -> dict[str, Any]:
    """Объяснение по портфелю: почему проекты в focus/hotspots."""
    rationales: List[dict] = []
    try:
        focus = __import__("app.services.owner_portfolio", fromlist=["get_portfolio_focus_list"]).get_portfolio_focus_list(limit=5)
        for p in focus.get("items", [])[:5]:
            pk = p.get("project_key", "")
            reason = p.get("reason", "")
            status = p.get("status", "")
            action = p.get("suggested_action", "")
            rationales.append(_rationale(
                "recommendation_rationale",
                "portfolio",
                pk,
                f"{pk}: {status} — {reason[:50]}",
                reason,
                reason,
                [f"Status: {status}", reason[:60]][:5],
                ["owner_portfolio"],
                "high",
                action,
                [{"project_key": pk}],
            ))
    except Exception:
        pass
    return {"rationales": rationales, "window_days": window_days}


def explain_role_view(role_key: str) -> dict[str, Any]:
    """Объяснение по role view: collaboration items."""
    rationales: List[dict] = []
    try:
        from app.services.collaboration_flows import get_role_collaboration_summary
        collab = get_role_collaboration_summary(role_key)
        for i in collab.get("collaboration_items", [])[:5]:
            ht = i.get("handoff_type", "")
            reason = i.get("reason", "")
            rationales.append(_rationale(
                "collaboration_rationale",
                "role",
                role_key,
                f"{ht}: {reason[:50]}",
                reason,
                reason,
                [ht, reason][:5],
                ["collaboration_flows"],
                "medium",
                None,
                [],
            ))
    except Exception:
        pass
    return {"role_key": role_key, "rationales": rationales}


def explain_collaboration(project_key: Optional[str] = None, window_days: int = 7) -> dict[str, Any]:
    """Объяснение collaboration: handoffs, hotspots."""
    rationales: List[dict] = []
    try:
        from app.services.collaboration_flows import get_collaboration_hotspots, get_cross_role_handoffs
        if project_key:
            from app.services.collaboration_flows import get_project_handoff_signals
            ph = get_project_handoff_signals(project_key)
            for h in ph.get("handoff_signals", [])[:5]:
                rationales.append(_rationale(
                    "collaboration_rationale",
                    "collaboration",
                    project_key,
                    f"{h.get('handoff_type', '')}: {h.get('handoff_reason', '')}",
                    h.get("evidence_summary", h.get("handoff_reason", "")),
                    h.get("handoff_reason", ""),
                    [h.get("evidence_summary", "")][:5],
                    ["collaboration_flows"],
                    "high",
                    f"Target: {h.get('recommended_next_role', '')}",
                    [{"project_key": project_key}],
                ))
        else:
            hotspots = get_collaboration_hotspots(window_days=window_days, limit=5)
            for h in hotspots[:5]:
                rationales.append(_rationale(
                    "collaboration_rationale",
                    "collaboration",
                    h.get("project_key", "") or "global",
                    f"{h.get('hotspot_type', '')}: {h.get('reason', '')[:50]}",
                    h.get("reason", ""),
                    h.get("reason", ""),
                    [h.get("evidence_summary", h.get("reason", ""))][:5],
                    ["collaboration_flows"],
                    "high" if h.get("severity") == "high" else "medium",
                    h.get("recommended_collaboration_action"),
                    [],
                ))
    except Exception as e:
        return {"rationales": [], "error": str(e)}
    return {"project_key": project_key, "rationales": rationales, "window_days": window_days}


def explain_refinement(proposal_id: Optional[str] = None, window_days: int = 30) -> dict[str, Any]:
    """Объяснение refinement: proposals, signals."""
    rationales: List[dict] = []
    try:
        if proposal_id:
            from app.services.refinement_proposals import get_refinement_proposal
            p = get_refinement_proposal(proposal_id)
            if p:
                rationales.append(_rationale(
                    "refinement_rationale",
                    "refinement",
                    proposal_id,
                    f"{p.get('proposal_type', '')}: {p.get('reason', '')[:50]}",
                    p.get("reason", ""),
                    p.get("reason", ""),
                    [p.get("evidence_summary", ""), p.get("recommended_change", "")][:5],
                    ["refinement_proposals"],
                    "high",
                    p.get("recommended_change"),
                    [{"proposal_id": proposal_id}],
                ))
        else:
            from app.services.refinement_proposals import list_refinement_proposals
            props = list_refinement_proposals(status="proposed", limit=5)
            for p in props[:5]:
                pid = p.get("proposal_id", "")
                rationales.append(_rationale(
                    "refinement_rationale",
                    "refinement",
                    pid,
                    f"{p.get('reason', '')[:60]}",
                    p.get("reason", ""),
                    p.get("reason", ""),
                    [p.get("evidence_summary", ""), p.get("recommended_change", "")][:5],
                    ["refinement_proposals"],
                    "medium",
                    p.get("recommended_change"),
                    [{"proposal_id": pid}],
                ))
    except Exception as e:
        return {"rationales": [], "error": str(e)}
    return {"proposal_id": proposal_id, "rationales": rationales, "window_days": window_days}


def explain_signal(signal_type: str, subject_key: Optional[str] = None, context: Optional[dict] = None) -> dict[str, Any]:
    """Объяснение по типу сигнала. Диспетчеризует на explain_*."""
    if signal_type in ("task", "task_id"):
        tid = subject_key and int(subject_key) if str(subject_key or "").isdigit() else (context or {}).get("task_id")
        if tid:
            return explain_task(int(tid))
    if signal_type in ("project", "project_key"):
        pk = subject_key or (context or {}).get("project_key") or "general"
        return explain_project(str(pk))
    if signal_type == "portfolio":
        return explain_portfolio()
    if signal_type in ("collaboration", "handoff"):
        pk = subject_key or (context or {}).get("project_key")
        return explain_collaboration(project_key=pk)
    if signal_type == "refinement":
        return explain_refinement(proposal_id=subject_key)
    if signal_type == "role":
        rk = subject_key or (context or {}).get("role_key") or "owner"
        return explain_role_view(rk)
    return {"rationales": [], "error": f"unknown signal_type: {signal_type}"}
