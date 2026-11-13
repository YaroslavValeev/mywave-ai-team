# app/services/intervention_planning.py — Phase 11.7: intervention bundles and prioritized plans
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _action_to_safe_key(action_type: str) -> Optional[str]:
    """Map recommendation action_type to action_center key where available."""
    m = {
        "approval": "open_decision_queue",
        "degraded": "recheck_molt_health",
    }
    return m.get(action_type)


def _action_to_intervention_type(action_type: str) -> str:
    m = {
        "approval": "approval",
        "degraded": "runtime_escalation",
        "blocker": "owner_attention",
        "rework": "owner_attention",
        "long_running": "owner_attention",
        "refinement_review": "refinement_review",
        "refinement_patch_apply": "refinement_patch",
        "refinement_patch_validation": "refinement_review",
        "tuning_review": "tuning_review",
        "patchable_tuning_candidate_signal": "tuning_patch",
        "tuning_outcome_needs_followup": "tuning_review",
        "failed_tuning_patch_signal": "tuning_review",
        "pending_collaboration_execution_attention": "collaboration_execution",
        "collaboration_execution_followup_signal": "collaboration_execution",
        "ineffective_collaboration_pattern_signal": "collaboration_resolution",
        "project_collaboration_needs_revisit": "project_intervention",
        "cross_layer_alignment_conflict_signal": "cross_layer_conflict",
        "project_domain_drift_requiring_intervention": "project_domain_refinement",
        "project_domain_diversification_requiring_review": "project_domain_refinement",
        "project_domain_evolution_attention": "project_domain_refinement",
    }
    return m.get(action_type, "owner_attention")


def _priority_order(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 1)


def _build_intervention_from_action(a: dict[str, Any], idx: int, scope_type: str, scope_key: str) -> dict[str, Any]:
    action_type = a.get("action_type", "owner_attention")
    safe_key = a.get("suggested_safe_action") or _action_to_safe_key(action_type)
    return {
        "intervention_id": f"iv_{scope_type}_{scope_key or 'x'}_{idx}",
        "intervention_type": _action_to_intervention_type(action_type),
        "target_layer": "governance" if action_type in ("approval", "tuning_review", "collaboration_execution") else "runtime" if action_type == "degraded" else "product",
        "target_role": "owner",
        "safe_action_available": bool(safe_key),
        "safe_action_key": safe_key,
        "manual_path_required": not bool(safe_key),
        "reason": a.get("reason", ""),
        "expected_effect": "Снятие bottleneck" if "bottleneck" in str(a.get("reason", "")) else "Стабилизация",
        "urgency": a.get("priority", "medium"),
        "task_id": a.get("task_id"),
        "action_type_source": action_type,
        "suggested_action": a.get("suggested_action"),
    }


def get_project_intervention_plan(project_key: str, window_days: int = 30) -> dict[str, Any]:
    """Project-level intervention plan."""
    interventions: List[dict[str, Any]] = []
    try:
        from app.services.collaboration_action_suggestions import get_project_action_suggestions, get_decision_support
        from app.services.collaboration_outcomes import list_collaboration_outcomes

        ds = get_decision_support("project", scope_key=project_key, window_days=window_days, limit=8)
        sug = get_project_action_suggestions(project_key, window_days=window_days, limit=8)
        for i, d in enumerate(ds.get("items", [])):
            opt = (d.get("options") or [{}])[0]
            interventions.append({
                "intervention_id": f"iv_project_{project_key}_{i}",
                "intervention_type": "project_intervention",
                "target_layer": "product",
                "target_role": "owner",
                "safe_action_available": bool(opt.get("action_hint") and "open_decision" in str(opt.get("action_hint", ""))),
                "safe_action_key": "open_decision_queue" if "approval" in str(d.get("headline", "")).lower() else None,
                "manual_path_required": True,
                "reason": d.get("why_now", ""),
                "expected_effect": "Проект разблокирован",
                "urgency": "medium",
                "headline": d.get("headline", ""),
            })
        outcomes = [o for o in list_collaboration_outcomes(window_days=window_days, limit=50).get("items", [])
                    if (o.get("subject_type") or "").lower() == "project" and str(o.get("subject_key")) == str(project_key)]
        if any(o.get("followup_needed") for o in outcomes):
            interventions.append({
                "intervention_id": f"iv_project_{project_key}_collab",
                "intervention_type": "collaboration_execution",
                "target_layer": "governance",
                "target_role": "owner",
                "safe_action_available": False,
                "safe_action_key": None,
                "manual_path_required": True,
                "reason": "Collaboration outcomes требуют follow-up по проекту",
                "expected_effect": "Повторная координация",
                "urgency": "low",
            })
    except Exception:
        pass

    try:
        from app.services.project_domain_evolution_refinement import get_project_domain_evolution_refinement
        ref = get_project_domain_evolution_refinement(project_key, window_days=window_days)
        if ref.get("intervention_needed"):
            interventions.append({
                "intervention_id": f"iv_project_{project_key}_domain_evolution",
                "intervention_type": "project_domain_refinement",
                "target_layer": "product",
                "target_role": "owner",
                "safe_action_available": False,
                "safe_action_key": None,
                "manual_path_required": True,
                "reason": ref.get("evidence_summary", [""])[0] or "Domain evolution требует внимания",
                "expected_effect": "Стабилизация доменного профиля",
                "urgency": "medium",
                "headline": ref.get("owner_answer", ""),
                "refinement_class": ref.get("refinement_class"),
            })
    except Exception:
        pass

    do_now = interventions[0] if interventions else None
    do_next = interventions[1] if len(interventions) > 1 else None
    defer = interventions[2:] if len(interventions) > 2 else []

    return {
        "plan_id": f"ip_project_{project_key}",
        "scope_type": "project",
        "scope_key": project_key,
        "plan_headline": f"Рекомендуемые вмешательства по проекту {project_key}",
        "plan_reason": "Сигналы и decision support по проекту",
        "priority_label": "high" if any(i.get("urgency") == "high" for i in interventions) else "medium",
        "interventions": interventions,
        "preferred_intervention": 0 if interventions else None,
        "fallback_intervention": 1 if len(interventions) > 1 else None,
        "expected_effect": "Разблокировка проекта" if interventions else None,
        "risk_if_ignored": "Проект может застрять",
        "evidence_refs": [{"id_type": "project_key", "id_value": project_key}],
        "generated_at": _now(),
        "do_now": do_now,
        "do_next": do_next,
        "defer": defer,
    }


def get_portfolio_intervention_plan(window_days: int = 30) -> dict[str, Any]:
    """Portfolio-level: top interventions from get_next_actions + ordering."""
    interventions: List[dict[str, Any]] = []
    try:
        from app.services.owner_recommendations import get_next_actions

        actions = get_next_actions(limit=25)
        items = actions.get("items", [])
        # Heuristic: high first, then medium, then low
        sorted_items = sorted(items, key=lambda x: (_priority_order(x.get("priority", "medium")), x.get("action_type", "")))

        # Cross-layer conflict first if present
        conflict_idx = next((i for i, a in enumerate(sorted_items) if a.get("action_type") == "cross_layer_alignment_conflict_signal"), None)
        if conflict_idx is not None:
            c = sorted_items.pop(conflict_idx)
            sorted_items.insert(0, c)

        # Degraded second
        deg_idx = next((i for i, a in enumerate(sorted_items) if a.get("action_type") == "degraded"), None)
        if deg_idx is not None and deg_idx > 0:
            d = sorted_items.pop(deg_idx)
            sorted_items.insert(1 if conflict_idx is not None else 0, d)

        # Project domain evolution (Phase 11.9)
        pd_idx = next((i for i, a in enumerate(sorted_items) if a.get("action_type") in ("project_domain_drift_requiring_intervention", "project_domain_evolution_attention")), None)
        if pd_idx is not None and pd_idx > 2:
            pd = sorted_items.pop(pd_idx)
            sorted_items.insert(min(2, len(sorted_items)), pd)

        for idx, a in enumerate(sorted_items[:12]):
            interventions.append(_build_intervention_from_action(a, idx, "portfolio", ""))

        # Phase 12.0: safe_action first for do_now when available
        with_safe = [i for i in interventions if i.get("safe_action_available")]
        if with_safe:
            with_safe.sort(key=lambda x: _priority_order(x.get("urgency", "medium")))
            rest = [i for i in interventions if not i.get("safe_action_available")]
            interventions = with_safe + rest

        do_now = interventions[0] if interventions else None
        do_next = interventions[1] if len(interventions) > 1 else None
        defer = interventions[2:] if len(interventions) > 2 else []

        return {
            "plan_id": "ip_portfolio",
            "scope_type": "portfolio",
            "scope_key": "",
            "plan_headline": "Приоритетные вмешательства по портфелю",
            "plan_reason": "Рекомендации owner + cross-layer synthesis",
            "priority_label": "high" if any(i.get("urgency") == "high" for i in interventions) else "medium",
            "interventions": interventions,
            "preferred_intervention": 0 if interventions else None,
            "fallback_intervention": 1 if len(interventions) > 1 else None,
            "expected_effect": "Стабилизация портфеля" if interventions else None,
            "risk_if_ignored": "Накопление backlog",
            "evidence_refs": [],
            "generated_at": _now(),
            "do_now": do_now,
            "do_next": do_next,
            "defer": defer,
        }
    except Exception:
        return {
            "plan_id": "ip_portfolio",
            "scope_type": "portfolio",
            "scope_key": "",
            "plan_headline": "Приоритетные вмешательства по портфелю",
            "plan_reason": "Ошибка загрузки",
            "priority_label": "medium",
            "interventions": [],
            "preferred_intervention": None,
            "fallback_intervention": None,
            "expected_effect": None,
            "risk_if_ignored": None,
            "evidence_refs": [],
            "generated_at": _now(),
            "do_now": None,
            "do_next": None,
            "defer": [],
        }


def get_cross_layer_intervention_plans(window_days: int = 30) -> dict[str, Any]:
    """Cross-layer conflict bundle."""
    interventions: List[dict[str, Any]] = []
    try:
        from app.services.cross_layer_effectiveness import get_layer_alignment_signals

        align = get_layer_alignment_signals(window_days=window_days)
        for idx, a in enumerate(align):
            interventions.append({
                "intervention_id": f"iv_cross_{idx}",
                "intervention_type": "cross_layer_conflict",
                "target_layer": "governance",
                "target_role": "owner",
                "safe_action_available": False,
                "safe_action_key": None,
                "manual_path_required": True,
                "reason": a.get("reason", a.get("headline", "")),
                "expected_effect": "Согласование слоёв",
                "urgency": "medium",
                "conflict_type": a.get("conflict_type"),
                "evidence_refs": a.get("evidence_refs", []),
            })

        do_now = interventions[0] if interventions else None
        do_next = interventions[1] if len(interventions) > 1 else None
        defer = interventions[2:] if len(interventions) > 2 else []

        return {
            "plan_id": "ip_cross_layer",
            "scope_type": "cross_layer",
            "scope_key": "",
            "plan_headline": "Рассогласование слоёв (collaboration vs tuning)",
            "plan_reason": "Cross-layer effectiveness synthesis",
            "priority_label": "medium" if interventions else "low",
            "interventions": interventions,
            "preferred_intervention": 0 if interventions else None,
            "fallback_intervention": 1 if len(interventions) > 1 else None,
            "expected_effect": "Согласование tuning и collaboration" if interventions else None,
            "risk_if_ignored": "Продолжающееся рассогласование",
            "evidence_refs": sum((a.get("evidence_refs", []) for a in align[:3]), []),
            "generated_at": _now(),
            "do_now": do_now,
            "do_next": do_next,
            "defer": defer,
        }
    except Exception:
        return {
            "plan_id": "ip_cross_layer",
            "scope_type": "cross_layer",
            "scope_key": "",
            "plan_headline": "Рассогласование слоёв",
            "plan_reason": "Ошибка загрузки",
            "priority_label": "low",
            "interventions": [],
            "preferred_intervention": None,
            "fallback_intervention": None,
            "expected_effect": None,
            "risk_if_ignored": None,
            "evidence_refs": [],
            "generated_at": _now(),
            "do_now": None,
            "do_next": None,
            "defer": [],
        }


def get_intervention_bundle(
    scope_type: str,
    scope_key: Optional[str] = None,
    window_days: int = 30,
) -> dict[str, Any]:
    """Unified intervention bundle dispatcher."""
    if scope_type == "project" and scope_key:
        plan = get_project_intervention_plan(scope_key, window_days=window_days)
    elif scope_type == "portfolio":
        plan = get_portfolio_intervention_plan(window_days=window_days)
    elif scope_type == "cross_layer":
        plan = get_cross_layer_intervention_plans(window_days=window_days)
    else:
        plan = get_portfolio_intervention_plan(window_days=window_days)

    bundle_type = {
        "project": "project_intervention_bundle",
        "portfolio": "portfolio_attention_bundle",
        "cross_layer": "cross_layer_conflict_bundle",
    }.get(scope_type, "portfolio_attention_bundle")

    do_now = plan.get("do_now")
    do_next = plan.get("do_next")
    defer = plan.get("defer", [])

    return {
        "decision_bundle_id": f"db_{bundle_type}_{scope_key or 'portfolio'}",
        "bundle_type": bundle_type,
        "subject_type": scope_type,
        "subject_key": scope_key or "",
        "headline": plan.get("plan_headline", ""),
        "why_now": plan.get("plan_reason", ""),
        "top_problem": (do_now or {}).get("reason", "")[:200] if do_now else "",
        "candidate_interventions": plan.get("interventions", []),
        "preferred_sequence": [plan.get("preferred_intervention"), plan.get("fallback_intervention")] if plan.get("preferred_intervention") is not None else [],
        "do_now": do_now,
        "do_next": do_next,
        "defer": defer,
        "evidence_summary": [r.get("id_value", "") for r in plan.get("evidence_refs", [])[:5]],
        "related_objects": [{"type": r.get("id_type"), "id": r.get("id_value")} for r in plan.get("evidence_refs", [])],
        "plan": plan,
    }


def list_priority_interventions(window_days: int = 30, limit: int = 10) -> dict[str, Any]:
    """Top interventions across portfolio + cross-layer."""
    items: List[dict[str, Any]] = []
    try:
        port = get_portfolio_intervention_plan(window_days=window_days)
        for i, iv in enumerate(port.get("interventions", [])[:5]):
            iv_copy = dict(iv)
            iv_copy["source_plan"] = "portfolio"
            iv_copy["source_scope_key"] = ""
            items.append(iv_copy)

        cross = get_cross_layer_intervention_plans(window_days=window_days)
        for i, iv in enumerate(cross.get("interventions", [])[:2]):
            iv_copy = dict(iv)
            iv_copy["source_plan"] = "cross_layer"
            iv_copy["source_scope_key"] = ""
            items.append(iv_copy)
    except Exception:
        pass
    return {"items": items[:limit], "count": len(items[:limit]), "window_days": window_days}


def get_task_intervention_plan(task_id: int, window_days: int = 7) -> dict[str, Any]:
    """Task-level: from decision_support task scope."""
    try:
        from app.services.collaboration_action_suggestions import get_decision_support

        ds = get_decision_support("task", scope_key=str(task_id), window_days=window_days, limit=5)
        interventions = []
        for i, d in enumerate(ds.get("items", [])):
            opt = (d.get("options") or [{}])[0]
            interventions.append({
                "intervention_id": f"iv_task_{task_id}_{i}",
                "intervention_type": "approval" if "approval" in str(d.get("headline", "")).lower() else "owner_attention",
                "target_layer": "governance",
                "target_role": "owner",
                "safe_action_available": bool("open_decision" in str(opt.get("action_hint", ""))),
                "safe_action_key": "open_decision_queue",
                "manual_path_required": True,
                "reason": d.get("why_now", ""),
                "expected_effect": "Решение по задаче",
                "urgency": "high",
                "task_id": task_id,
            })
        do_now = interventions[0] if interventions else None
        return {
            "plan_id": f"ip_task_{task_id}",
            "scope_type": "task",
            "scope_key": str(task_id),
            "plan_headline": f"Вмешательства по задаче #{task_id}",
            "plan_reason": "Decision support по задаче",
            "priority_label": "high" if interventions else "medium",
            "interventions": interventions,
            "preferred_intervention": 0 if interventions else None,
            "fallback_intervention": None,
            "expected_effect": "Разблокировка задачи" if interventions else None,
            "risk_if_ignored": "Задача останется в подвешенном состоянии",
            "evidence_refs": [{"id_type": "task_id", "id_value": str(task_id)}],
            "generated_at": _now(),
            "do_now": do_now,
            "do_next": None,
            "defer": [],
        }
    except Exception:
        return {
            "plan_id": f"ip_task_{task_id}",
            "scope_type": "task",
            "scope_key": str(task_id),
            "plan_headline": "Ошибка загрузки",
            "plan_reason": "",
            "priority_label": "medium",
            "interventions": [],
            "preferred_intervention": None,
            "fallback_intervention": None,
            "expected_effect": None,
            "risk_if_ignored": None,
            "evidence_refs": [],
            "generated_at": _now(),
            "do_now": None,
            "do_next": None,
            "defer": [],
        }
