# app/dashboard/app.py — FastAPI + Jinja (HF-1: auth, v0.2 Control API)
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_dashboard_config
from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.auth import require_owner_key
from app.shared.redaction import redact, scrub_secrets
from app.dashboard.api_router import router as api_router
from app.services.owner_dashboard import (
    get_dashboard_overview,
    get_dashboard_next_actions,
    get_dashboard_blockers,
    get_dashboard_decision_queue,
    get_dashboard_project_health,
    get_dashboard_recent_artifacts,
    get_dashboard_digest_preview,
)
from app.presenters.owner_dashboard_presenters import (
    present_dashboard_overview,
    present_dashboard_next_actions,
    present_dashboard_blockers,
    present_dashboard_decision_queue,
    present_dashboard_project_health,
    present_dashboard_recent_artifacts,
    present_dashboard_digest_preview,
)
from app.services.project_queries import (
    list_projects,
    get_project_overview,
    get_project_health,
    get_project_tasks,
    get_project_pending_approvals,
    get_project_recent_artifacts,
    get_project_risks,
    get_project_decision_queue,
)
from app.presenters.project_presenters import (
    present_project_list,
    present_project_overview,
    present_project_health,
    present_project_tasks,
    present_project_approvals,
    present_project_artifacts,
    present_project_risks,
    present_project_decision_queue,
)
from app.services.owner_portfolio import (
    get_portfolio_overview,
    get_top_problem_projects,
    get_approvals_backlog_by_project,
    get_rework_hotspots,
    get_degraded_hotspots,
    get_portfolio_focus_list,
    get_portfolio_digest,
)
from app.presenters.owner_portfolio_presenters import (
    present_portfolio_overview,
    present_top_problem_projects,
    present_approvals_backlog_by_project,
    present_rework_hotspots,
    present_degraded_hotspots,
    present_portfolio_focus_list,
    present_portfolio_digest,
)
from app.services.role_views import get_owner_view, get_operator_view, get_executor_view, get_reviewer_view
from app.services.collaboration_flows import (
    get_collaboration_hotspots,
    get_collaboration_recommendations,
    get_cross_role_handoffs,
    get_project_handoff_signals,
    get_role_collaboration_summary,
)
from app.presenters.role_presenters import (
    present_operator_view,
    present_executor_view,
    present_reviewer_view,
)
from app.services.action_center import list_available_actions, can_execute_action, execute_action
from app.services.role_access import (
    resolve_actor_role,
    deny_or_fallback_role,
    resolve_and_log,
    check_action_access_and_log,
    get_role_access_summary,
    log_critical_route_access_if_enabled,
)
from app.presenters.action_presenters import format_action_list, format_action_result, format_action_error
from app.presenters.role_access_presenters import (
    format_access_denied_message,
    present_access_denied,
)
from app.services.production_readiness import get_production_readiness_summary
from app.presenters.production_readiness_presenters import (
    present_readiness_card,
    present_failed_checks_summary,
    format_readiness_owner_text,
)
from app.services.domain_registry import list_domains, get_domain, get_expert_profile
from app.services.expert_routing import suggest_domains_for_task
from app.presenters.domain_presenters import (
    present_domain_registry_list,
    present_domain_card,
    present_expert_profile,
    present_routing_result,
)
from app.services.domain_specialization_analytics import (
    get_domain_override_summary,
    get_override_hotspots,
    get_specialization_fallback_summary,
    get_specialization_hotspots,
    get_refinement_signals,
    get_refinement_backlog,
)
from app.presenters.domain_specialization_analytics_presenters import (
    present_domain_override_summary,
    present_override_hotspots,
    present_specialization_fallback_summary,
    present_specialization_hotspots,
    present_refinement_signals,
    present_refinement_backlog,
)
from app.services.refinement_proposals import (
    generate_refinement_proposals,
    list_refinement_proposals,
    get_refinement_proposal,
    review_refinement_proposal,
    mark_refinement_proposal_applied,
)
from app.services.agent_tuning_workflows import (
    get_tuning_candidates,
    get_tuning_candidate,
    get_specialization_tuning_summary,
    generate_tuning_candidates,
    mark_tuning_candidate_reviewed,
    convert_tuning_candidate_to_proposal,
    mark_tuning_candidate_verified,
)
from app.presenters.agent_tuning_presenters import (
    present_tuning_candidate_list,
    present_tuning_candidate_card,
    present_tuning_summary,
)
from app.services.tuning_patch_integration import (
    list_patchable_tuning_candidates,
    list_manual_tuning_candidates,
    get_tuning_patch_summary,
    classify_tuning_candidate_patchability,
    build_patch_from_tuning_candidate,
)
from app.services.tuning_outcomes import (
    evaluate_tuning_outcome,
    get_tuning_outcome,
    list_tuning_outcomes,
    get_tuning_outcome_summary,
)
from app.presenters.tuning_patch_presenters import (
    present_patchable_tuning_candidate,
    present_tuning_patch_summary,
    present_tuning_outcome,
    present_tuning_outcome_summary,
    present_patchability_card,
)
from app.services.refinement_exports import export_refinement_proposal, export_pending_refinement_changes
from app.services.registry_patch_builder import build_patch_candidate
from app.services.registry_patch_apply import dry_run_patch, validate_patch_candidate, apply_patch_candidate, rollback_patch
from app.presenters.refinement_proposal_presenters import (
    present_refinement_proposal_list,
    present_refinement_proposal_card,
    present_refinement_review_result,
    present_refinement_export,
)
from app.services.explanation_assist import explain_task, explain_project, explain_portfolio, explain_collaboration, explain_refinement
from app.presenters.explanation_presenters import (
    present_task_explanation,
    present_project_explanation,
    present_portfolio_explanation,
    present_collaboration_explanation,
    present_refinement_explanation,
)
from app.presenters.collaboration_presenters import (
    present_cross_role_handoffs,
    present_collaboration_hotspots,
    present_collaboration_recommendations,
    present_project_handoff_signals,
    present_role_collaboration_summary,
)
from app.services.collaboration_action_suggestions import (
    get_task_action_suggestions,
    get_project_action_suggestions,
    get_portfolio_action_suggestions,
    get_role_action_suggestions,
    get_collaboration_action_suggestions,
    get_decision_support,
)
from app.presenters.action_suggestion_presenters import (
    present_action_suggestion_list,
    present_decision_support_list,
)
from app.services.collaboration_execution import (
    list_collaboration_executions,
    get_collaboration_execution,
    build_execution_from_suggestion,
    trigger_collaboration_execution,
    mark_collaboration_execution_closed,
    get_collaboration_execution_summary,
    get_pending_collaboration_executions,
)
from app.presenters.collaboration_execution_presenters import (
    present_collaboration_execution_card,
    present_collaboration_execution_list,
    present_collaboration_execution_summary,
    present_collaboration_execution_result,
)
from app.services.collaboration_outcomes import (
    evaluate_collaboration_execution_outcome,
    get_collaboration_execution_outcome,
    list_collaboration_outcomes,
    get_collaboration_effectiveness_summary,
    get_collaboration_effectiveness_hotspots,
    get_followup_needed_executions,
)
from app.presenters.collaboration_outcome_presenters import (
    present_collaboration_outcome_card,
    present_collaboration_outcome_list,
    present_collaboration_effectiveness_summary,
    present_collaboration_effectiveness_hotspots,
    present_followup_needed_items,
)
from app.services.cross_layer_effectiveness import synthesize_cross_layer_summary
from app.presenters.cross_layer_effectiveness_presenters import present_cross_layer_synthesis
from app.services.intervention_planning import (
    get_project_intervention_plan,
    get_portfolio_intervention_plan,
    get_cross_layer_intervention_plans,
    get_intervention_bundle,
    list_priority_interventions,
)
from app.presenters.intervention_presenters import (
    present_intervention_plan,
    present_intervention_bundle,
    present_priority_interventions,
)
from app.presenters.registry_patch_presenters import (
    present_patch_candidate,
    present_patch_dry_run,
    present_patch_validation,
    present_patch_apply_result,
    present_patch_error,
)

app = FastAPI(title="MyWave AI-TEAM Dashboard", version="0.2.0")
app.include_router(api_router)

# Reconcile: preserve live mission/office/execution-pack surface alongside productization.
from app.dashboard.runtime_mission_routes import router as runtime_mission_router

app.include_router(runtime_mission_router)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Static assets (live runtime templates/mission UI)
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/health")
async def health():
    """Без auth — для healthcheck."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {}
    )


@app.get("/owner", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_dashboard(request: Request):
    """Phase 9.4: read-only owner dashboard — overview, next actions, blockers, decisions, health, artifacts, digests."""
    overview_raw = get_dashboard_overview()
    next_actions_raw = get_dashboard_next_actions(limit=5)
    blockers_raw = get_dashboard_blockers(limit=10)
    decision_queue_raw = get_dashboard_decision_queue(limit=10)
    project_health_raw = get_dashboard_project_health(limit=10)
    recent_artifacts_raw = get_dashboard_recent_artifacts(limit=10)
    digest_raw = get_dashboard_digest_preview()

    overview = present_dashboard_overview(overview_raw)
    next_actions = present_dashboard_next_actions(next_actions_raw)
    blockers = present_dashboard_blockers(blockers_raw)
    decision_queue = present_dashboard_decision_queue(decision_queue_raw)
    project_health = present_dashboard_project_health(project_health_raw)
    recent_artifacts = present_dashboard_recent_artifacts(recent_artifacts_raw)
    digest_preview = present_dashboard_digest_preview(digest_raw)
    collaboration_hotspots = present_collaboration_hotspots(get_collaboration_hotspots(window_days=7, limit=5))
    cross_layer_synthesis = None
    try:
        cross_layer_synthesis = present_cross_layer_synthesis(synthesize_cross_layer_summary(window_days=30))
    except Exception:
        pass

    readiness = None
    try:
        readiness = present_readiness_card(get_production_readiness_summary())
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "owner_dashboard.html",
        {
            "overview": overview,
            "readiness": readiness,
            "next_actions": next_actions,
            "blockers": blockers,
            "decision_queue": decision_queue,
            "project_health": project_health,
            "recent_artifacts": recent_artifacts,
            "digest_preview": digest_preview,
            "collaboration_hotspots": collaboration_hotspots,
            "cross_layer_synthesis": cross_layer_synthesis},
    )


@app.get("/owner/portfolio", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_portfolio_page(request: Request, window_days: int = 30):
    """Phase 9.6 / 10.8: portfolio (cross-project) view + domain lifecycle."""
    overview_raw = get_portfolio_overview()
    top_problem_raw = get_top_problem_projects(limit=10)
    backlog_raw = get_approvals_backlog_by_project(limit=15)
    rework_raw = get_rework_hotspots(limit=10)
    degraded_raw = get_degraded_hotspots(limit=10)
    focus_raw = get_portfolio_focus_list(limit=5)
    digest_raw = get_portfolio_digest(window_days=7)

    overview = present_portfolio_overview(overview_raw)
    top_problem = present_top_problem_projects(top_problem_raw)
    backlog = present_approvals_backlog_by_project(backlog_raw)
    rework = present_rework_hotspots(rework_raw)
    degraded = present_degraded_hotspots(degraded_raw)
    focus = present_portfolio_focus_list(focus_raw)
    digest = present_portfolio_digest(digest_raw)

    lifecycle_summary = None
    evolution_transition_summary = None
    try:
        from app.services.project_domain_lifecycle import get_cross_project_domain_lifecycle_summary
        from app.presenters.project_domain_lifecycle_presenters import present_cross_project_domain_lifecycle_summary
        lifecycle_summary = present_cross_project_domain_lifecycle_summary(get_cross_project_domain_lifecycle_summary(window_days=window_days))
    except Exception:
        pass
    try:
        from app.services.project_domain_evolution_refinement import get_project_domain_transition_summary
        from app.presenters.project_domain_evolution_presenters import present_attention_items
        ev_raw = get_project_domain_transition_summary(window_days=window_days)
        evolution_transition_summary = {
            "window_days": ev_raw.get("window_days"),
            "attention_items_count": ev_raw.get("attention_items_count", 0),
            "drift_requiring_intervention_count": ev_raw.get("drift_requiring_intervention_count", 0),
            "diversification_requiring_review_count": ev_raw.get("diversification_requiring_review_count", 0),
            "attention_items": present_attention_items(ev_raw.get("attention_items", [])).get("items", [])}
    except Exception:
        pass

    collaboration_hotspots = present_collaboration_hotspots(get_collaboration_hotspots(window_days=window_days, limit=10))
    portfolio_explanation = None
    try:
        portfolio_explanation = present_portfolio_explanation(explain_portfolio(window_days=window_days))
    except Exception:
        pass

    portfolio_decision_support = None
    try:
        ds_raw = get_decision_support("portfolio", scope_key=None, window_days=window_days, limit=5)
        portfolio_decision_support = present_decision_support_list(ds_raw.get("items", []))
    except Exception:
        pass

    portfolio_collab_executions = None
    try:
        pe = get_pending_collaboration_executions(window_days=min(window_days, 14), limit=10)
        portfolio_collab_executions = present_collaboration_execution_list(pe.get("items", []))
    except Exception:
        pass

    portfolio_collab_outcome_summary = None
    try:
        portfolio_collab_outcome_summary = present_collaboration_effectiveness_summary(
            get_collaboration_effectiveness_summary(window_days=min(window_days, 30))
        )
    except Exception:
        pass

    portfolio_cross_layer_synthesis = None
    try:
        portfolio_cross_layer_synthesis = present_cross_layer_synthesis(
            synthesize_cross_layer_summary(window_days=min(window_days, 30))
        )
    except Exception:
        pass

    portfolio_intervention_plans = None
    portfolio_cross_layer_bundle = None
    try:
        port_plan = get_portfolio_intervention_plan(window_days=window_days)
        portfolio_intervention_plans = present_intervention_plan(port_plan)
        cross_bundle = get_intervention_bundle("cross_layer", window_days=window_days)
        portfolio_cross_layer_bundle = present_intervention_bundle(cross_bundle) if cross_bundle.get("candidate_interventions") else None
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "owner_portfolio.html",
        {
            "overview": overview,
            "top_problem": top_problem,
            "backlog": backlog,
            "rework": rework,
            "degraded": degraded,
            "focus": focus,
            "digest": digest,
            "lifecycle_summary": lifecycle_summary,
            "evolution_transition_summary": evolution_transition_summary,
            "collaboration_hotspots": collaboration_hotspots,
            "portfolio_explanation": portfolio_explanation,
            "portfolio_decision_support": portfolio_decision_support,
            "portfolio_collab_executions": portfolio_collab_executions,
            "portfolio_collab_outcome_summary": portfolio_collab_outcome_summary,
            "portfolio_cross_layer_synthesis": portfolio_cross_layer_synthesis,
            "portfolio_intervention_plans": portfolio_intervention_plans,
            "portfolio_cross_layer_bundle": portfolio_cross_layer_bundle},
    )


@app.get("/owner/effectiveness", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_effectiveness_page(request: Request, window_days: int = 30):
    """Phase 11.6: cross-layer effectiveness synthesis (tuning + collaboration)."""
    raw = synthesize_cross_layer_summary(window_days=window_days)
    # Starlette>=0.37: TemplateResponse(request, name, context)
    return templates.TemplateResponse(
        request,
        "owner_effectiveness.html",
        {"synthesis": present_cross_layer_synthesis(raw)},
    )


@app.get("/owner/collaboration/outcomes", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_collaboration_outcomes_page(request: Request, window_days: int = 30):
    """Phase 11.5: список collaboration outcomes + сводка эффективности."""
    outcomes_raw = list_collaboration_outcomes(window_days=window_days, limit=80)
    summary_raw = get_collaboration_effectiveness_summary(window_days=window_days)
    hotspots_raw = get_collaboration_effectiveness_hotspots(window_days=window_days, limit=15)
    follow_raw = get_followup_needed_executions(window_days=window_days, limit=25)
    return templates.TemplateResponse(
        request,
        "owner_collaboration_outcomes.html",
        {
            "window_days": window_days,
            "outcomes": present_collaboration_outcome_list(outcomes_raw.get("items", [])),
            "summary": present_collaboration_effectiveness_summary(summary_raw),
            "hotspots": present_collaboration_effectiveness_hotspots(hotspots_raw),
            "followup": present_followup_needed_items(follow_raw)},
    )


@app.get("/owner/collaboration/executions", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_collaboration_executions_page(request: Request, window_days: int = 7):
    """Phase 11.4: список collaboration executions."""
    pending = get_pending_collaboration_executions(window_days=window_days, limit=50)
    closed = list_collaboration_executions(status="closed", limit=15)
    summary = present_collaboration_execution_summary(get_collaboration_execution_summary(window_days=window_days))
    return templates.TemplateResponse(
        request,
        "owner_collaboration_executions.html",
        {
            "window_days": window_days,
            "pending": present_collaboration_execution_list(pending.get("items", [])),
            "closed": present_collaboration_execution_list(closed),
            "summary": summary},
    )


@app.get("/owner/collaboration/execution/{execution_id}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_collaboration_execution_detail(request: Request, execution_id: str):
    """Phase 11.4: карточка execution."""
    import json as _json

    ex = get_collaboration_execution(execution_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Execution not found")
    snap = ex.get("suggestion_snapshot") or {}
    try:
        snap_txt = _json.dumps(snap, ensure_ascii=False, indent=2)
    except Exception:
        snap_txt = str(snap)
    outcome_card = None
    try:
        outcome_card = present_collaboration_outcome_card(get_collaboration_execution_outcome(execution_id) or {})
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "owner_collaboration_execution_detail.html",
        {
            "execution": present_collaboration_execution_card(ex),
            "raw": ex,
            "suggestion_snapshot_json": snap_txt,
            "outcome": outcome_card},
    )


@app.get("/owner/collaboration", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_collaboration_page(request: Request, window_days: int = 7):
    """Phase 10.9: collaboration dashboard — handoffs, hotspots, role bottlenecks, project recommendations."""
    handoffs_raw = get_cross_role_handoffs(window_days=window_days, limit=20)
    hotspots_raw = get_collaboration_hotspots(window_days=window_days, limit=15)
    recs_raw = get_collaboration_recommendations(window_days=window_days, limit=15)
    handoffs = present_cross_role_handoffs(handoffs_raw)
    hotspots = present_collaboration_hotspots(hotspots_raw)
    recs = present_collaboration_recommendations(recs_raw)
    collab_explanation = None
    try:
        collab_explanation = present_collaboration_explanation(explain_collaboration(project_key=None, window_days=window_days))
    except Exception:
        pass
    collab_exec_pending = None
    collab_exec_closed = None
    collab_exec_summary = None
    collab_outcome_summary = None
    try:
        pe = get_pending_collaboration_executions(window_days=window_days, limit=12)
        collab_exec_pending = present_collaboration_execution_list(pe.get("items", []))
        collab_exec_closed = present_collaboration_execution_list(list_collaboration_executions(status="closed", limit=8))
        collab_exec_summary = present_collaboration_execution_summary(get_collaboration_execution_summary(window_days=window_days))
    except Exception:
        pass
    try:
        wd = max(window_days, 14)
        collab_outcome_summary = present_collaboration_effectiveness_summary(
            get_collaboration_effectiveness_summary(window_days=wd)
        )
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "owner_collaboration.html",
        {
            "window_days": window_days,
            "handoffs": handoffs,
            "hotspots": hotspots,
            "recommendations": recs,
            "collaboration_explanation": collab_explanation,
            "collab_exec_pending": collab_exec_pending,
            "collab_exec_closed": collab_exec_closed,
            "collab_exec_summary": collab_exec_summary,
            "collab_outcome_summary": collab_outcome_summary},
    )


@app.get("/api/owner/collaboration", dependencies=[Depends(require_owner_key)])
async def api_owner_collaboration(window_days: int = 7):
    """Phase 10.9: JSON collaboration summary."""
    handoffs = get_cross_role_handoffs(window_days=window_days, limit=20)
    hotspots = get_collaboration_hotspots(window_days=window_days, limit=15)
    recs = get_collaboration_recommendations(window_days=window_days, limit=15)
    return {
        "window_days": window_days,
        "handoffs": handoffs,
        "hotspots": hotspots,
        "recommendations": recs}


@app.get("/api/owner/collaboration/executions", dependencies=[Depends(require_owner_key)])
async def api_collaboration_executions_list(status: str | None = None, limit: int = 50):
    """Phase 11.4: JSON список executions."""
    items = list_collaboration_executions(status=status, limit=limit)
    return present_collaboration_execution_list(items)


@app.get("/api/owner/collaboration/executions/{execution_id}", dependencies=[Depends(require_owner_key)])
async def api_collaboration_execution_get(execution_id: str):
    """Phase 11.4: JSON одна execution."""
    ex = get_collaboration_execution(execution_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Execution not found")
    return present_collaboration_execution_card(ex)


@app.post("/api/owner/collaboration/executions/from-suggestion", dependencies=[Depends(require_owner_key)])
async def api_collaboration_execution_from_suggestion(request: Request):
    """Phase 11.4: создать execution из тела suggestion."""
    body = await request.json()
    sug = body.get("suggestion") if isinstance(body, dict) else None
    if not sug:
        raise HTTPException(status_code=400, detail="Body must contain {suggestion: {...}}")
    ex = build_execution_from_suggestion(sug)
    if not ex:
        raise HTTPException(status_code=400, detail="Could not build execution")
    return present_collaboration_execution_result(ex)


@app.post("/api/owner/collaboration/executions/{execution_id}/trigger", dependencies=[Depends(require_owner_key)])
async def api_collaboration_execution_trigger(execution_id: str, request: Request):
    """Phase 11.4: trigger execution (optional safe action)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    actor = (body or {}).get("actor", "web")
    run_safe = (body or {}).get("run_safe_action", True)
    ex = trigger_collaboration_execution(execution_id, actor=actor, run_safe_action=run_safe)
    if not ex:
        raise HTTPException(status_code=400, detail="Cannot trigger")
    return present_collaboration_execution_result(ex)


@app.post("/api/owner/collaboration/executions/{execution_id}/close", dependencies=[Depends(require_owner_key)])
async def api_collaboration_execution_close(execution_id: str, request: Request):
    """Phase 11.4: закрыть execution."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    actor = (body or {}).get("actor", "web")
    reason = (body or {}).get("reason", "closed")
    ex = mark_collaboration_execution_closed(execution_id, actor=actor, reason=reason)
    if not ex:
        raise HTTPException(status_code=404, detail="Execution not found")
    return present_collaboration_execution_result(ex)


@app.get("/api/owner/effectiveness/synthesis", dependencies=[Depends(require_owner_key)])
async def api_owner_effectiveness_synthesis(window_days: int = 30):
    """Phase 11.6: JSON cross-layer synthesis."""
    return present_cross_layer_synthesis(synthesize_cross_layer_summary(window_days=window_days))


# Phase 11.7 / 12.0: intervention planning + adaptive decision support
@app.post("/owner/interventions/defer", response_class=RedirectResponse, dependencies=[Depends(require_owner_key)])
async def owner_interventions_defer_form(request: Request, window_days: int = 30):
    """Phase 12.3: form POST defer — redirect back to interventions."""
    from urllib.parse import quote
    try:
        form = await request.form()
        intervention_id = (form.get("intervention_id") or "").strip()
    except Exception:
        intervention_id = ""
    if not intervention_id:
        return RedirectResponse(url="/owner/interventions?error=intervention_id_required", status_code=303)
    from app.services.intervention_acceptance import record_intervention_response
    result = record_intervention_response(intervention_id, response="deferred", actor="web")
    if result.get("success"):
        return RedirectResponse(url="/owner/interventions?deferred=1", status_code=303)
    return RedirectResponse(url="/owner/interventions?error=" + quote(str(result.get("error", "unknown"))[:80]), status_code=303)


@app.get("/owner/interventions", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_interventions_page(request: Request, window_days: int = 30):
    """Phase 11.7/12.0: intervention plans and adaptive decision support."""
    port_plan = get_portfolio_intervention_plan(window_days=window_days)
    cross_plan = get_cross_layer_intervention_plans(window_days=window_days)
    priority_raw = list_priority_interventions(window_days=window_days, limit=10)
    adaptive_ds = None
    try:
        from app.services.adaptive_decision_support import get_portfolio_decision_support
        from app.presenters.adaptive_decision_support_presenters import present_adaptive_decision_support
        ads_raw = get_portfolio_decision_support(window_days=window_days)
        adaptive_ds = present_adaptive_decision_support(ads_raw)
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "owner_interventions.html",
        {
            "window_days": window_days,
            "adaptive_ds": adaptive_ds,
            "portfolio_plan": present_intervention_plan(port_plan),
            "cross_layer_plan": present_intervention_plan(cross_plan),
            "priority_interventions": present_priority_interventions(priority_raw)},
    )


@app.get("/api/owner/interventions", dependencies=[Depends(require_owner_key)])
async def api_owner_interventions(window_days: int = 30):
    """Phase 11.7: JSON priority interventions."""
    raw = list_priority_interventions(window_days=window_days, limit=10)
    return present_priority_interventions(raw)


@app.get("/api/owner/intervention/project/{project_key}", dependencies=[Depends(require_owner_key)])
async def api_owner_intervention_project(project_key: str, window_days: int = 30):
    """Phase 11.7: JSON project intervention bundle."""
    bundle = get_intervention_bundle("project", scope_key=project_key, window_days=window_days)
    return present_intervention_bundle(bundle)


@app.get("/api/owner/intervention/portfolio", dependencies=[Depends(require_owner_key)])
async def api_owner_intervention_portfolio(window_days: int = 30):
    """Phase 11.7: JSON portfolio intervention bundle."""
    bundle = get_intervention_bundle("portfolio", window_days=window_days)
    return present_intervention_bundle(bundle)


@app.get("/api/owner/intervention/cross-layer", dependencies=[Depends(require_owner_key)])
async def api_owner_intervention_cross_layer(window_days: int = 30):
    """Phase 11.7: JSON cross-layer intervention bundle."""
    bundle = get_intervention_bundle("cross_layer", window_days=window_days)
    return present_intervention_bundle(bundle)


@app.post("/api/owner/intervention/defer", dependencies=[Depends(require_owner_key)])
async def api_owner_intervention_defer(request: Request):
    """Phase 12.3: отложить intervention на 24ч."""
    from fastapi.responses import JSONResponse
    body = await request.json() if request.headers.get("content-type", "").find("json") >= 0 else {}
    if not body:
        try:
            form = await request.form()
            body = dict(form)
        except Exception:
            pass
    intervention_id = (body.get("intervention_id") or request.query_params.get("intervention_id") or "").strip()
    if not intervention_id:
        return JSONResponse({"success": False, "error": "intervention_id required"}, status_code=400)
    from app.services.intervention_acceptance import record_intervention_response
    result = record_intervention_response(intervention_id, response="deferred", actor="web")
    if result.get("success"):
        return result
    return JSONResponse(result, status_code=400)


# Phase 12.0: adaptive decision support API
@app.get("/api/owner/decision-support/task/{task_id}", dependencies=[Depends(require_owner_key)])
async def api_adaptive_decision_support_task(task_id: int, window_days: int = 7):
    """Phase 12.0: adaptive decision support for task."""
    from app.services.adaptive_decision_support import get_task_decision_support
    from app.presenters.adaptive_decision_support_presenters import present_adaptive_decision_support
    raw = get_task_decision_support(task_id, window_days=window_days)
    return present_adaptive_decision_support(raw)


@app.get("/api/owner/decision-support/project/{project_key}", dependencies=[Depends(require_owner_key)])
async def api_adaptive_decision_support_project(project_key: str, window_days: int = 30):
    """Phase 12.0: adaptive decision support for project."""
    from app.services.adaptive_decision_support import get_project_decision_support
    from app.presenters.adaptive_decision_support_presenters import present_adaptive_decision_support
    raw = get_project_decision_support(project_key, window_days=window_days)
    return present_adaptive_decision_support(raw)


@app.get("/api/owner/decision-support/portfolio", dependencies=[Depends(require_owner_key)])
async def api_adaptive_decision_support_portfolio(window_days: int = 30):
    """Phase 12.0: adaptive decision support for portfolio."""
    from app.services.adaptive_decision_support import get_portfolio_decision_support
    from app.presenters.adaptive_decision_support_presenters import present_adaptive_decision_support
    raw = get_portfolio_decision_support(window_days=window_days)
    return present_adaptive_decision_support(raw)


@app.get("/api/owner/decision-support/cross-layer", dependencies=[Depends(require_owner_key)])
async def api_adaptive_decision_support_cross_layer(window_days: int = 30):
    """Phase 12.0: adaptive decision support for cross-layer."""
    from app.services.adaptive_decision_support import get_cross_layer_decision_support
    from app.presenters.adaptive_decision_support_presenters import present_adaptive_decision_support
    raw = get_cross_layer_decision_support(window_days=window_days)
    return present_adaptive_decision_support(raw)


@app.get("/api/owner/decision-support/top", dependencies=[Depends(require_owner_key)])
async def api_adaptive_decision_support_top(window_days: int = 30, limit: int = 8):
    """Phase 12.0: top decision support items."""
    from app.services.adaptive_decision_support import list_top_decision_support_items
    from app.presenters.adaptive_decision_support_presenters import present_top_decision_support_items
    raw = list_top_decision_support_items(window_days=window_days, limit=limit)
    return present_top_decision_support_items(raw)


@app.get("/api/owner/collaboration/outcomes", dependencies=[Depends(require_owner_key)])
async def api_collaboration_outcomes_list(window_days: int = 30, limit: int = 80):
    """Phase 11.5: JSON outcomes."""
    raw = list_collaboration_outcomes(window_days=window_days, limit=limit)
    return present_collaboration_outcome_list(raw.get("items", []))


@app.get("/api/owner/collaboration/outcomes/summary", dependencies=[Depends(require_owner_key)])
async def api_collaboration_outcomes_summary(window_days: int = 30):
    return present_collaboration_effectiveness_summary(get_collaboration_effectiveness_summary(window_days=window_days))


@app.get("/api/owner/collaboration/outcomes/hotspots", dependencies=[Depends(require_owner_key)])
async def api_collaboration_outcomes_hotspots(window_days: int = 30, limit: int = 15):
    return present_collaboration_effectiveness_hotspots(
        get_collaboration_effectiveness_hotspots(window_days=window_days, limit=limit)
    )


@app.get("/api/owner/collaboration/outcomes/followup", dependencies=[Depends(require_owner_key)])
async def api_collaboration_outcomes_followup(window_days: int = 30, limit: int = 40):
    return present_followup_needed_items(get_followup_needed_executions(window_days=window_days, limit=limit))


@app.get(
    "/api/owner/collaboration/outcomes/execution/{execution_id}",
    dependencies=[Depends(require_owner_key)],
)
async def api_collaboration_outcome_for_execution(execution_id: str):
    o = get_collaboration_execution_outcome(execution_id)
    return present_collaboration_outcome_card(o or {})


@app.post(
    "/api/owner/collaboration/outcomes/execution/{execution_id}/evaluate",
    dependencies=[Depends(require_owner_key)],
)
async def api_collaboration_outcome_evaluate(execution_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    wd = int((body or {}).get("window_days", 7))
    rec = evaluate_collaboration_execution_outcome(execution_id, window_days=wd)
    if not rec:
        raise HTTPException(status_code=404, detail="Execution not found")
    return present_collaboration_outcome_card(rec)


@app.get("/api/explain/task/{task_id}", dependencies=[Depends(require_owner_key)])
async def api_explain_task(task_id: int):
    """Phase 11.0: unified rationale for task."""
    raw = explain_task(task_id)
    return raw


@app.get("/api/explain/project/{project_key}", dependencies=[Depends(require_owner_key)])
async def api_explain_project(project_key: str, window_days: int = 30):
    """Phase 11.0: unified rationale for project."""
    return explain_project(project_key, window_days=window_days)


@app.get("/api/explain/portfolio", dependencies=[Depends(require_owner_key)])
async def api_explain_portfolio(window_days: int = 7):
    """Phase 11.0: unified rationale for portfolio."""
    return explain_portfolio(window_days=window_days)


@app.get("/api/explain/collaboration", dependencies=[Depends(require_owner_key)])
async def api_explain_collaboration(project_key: str | None = None, window_days: int = 7):
    """Phase 11.0: unified rationale for collaboration."""
    return explain_collaboration(project_key=project_key, window_days=window_days)


@app.get("/api/explain/refinement", dependencies=[Depends(require_owner_key)])
async def api_explain_refinement_list(window_days: int = 30):
    """Phase 11.0: unified rationale for refinement proposals."""
    return explain_refinement(proposal_id=None, window_days=window_days)


@app.get("/api/explain/refinement/{proposal_id}", dependencies=[Depends(require_owner_key)])
async def api_explain_refinement_proposal(proposal_id: str, window_days: int = 30):
    """Phase 11.0: unified rationale for single refinement proposal."""
    return explain_refinement(proposal_id=proposal_id, window_days=window_days)


@app.get("/owner/decision-support", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_decision_support_page(request: Request, scope_type: str = "portfolio", scope_key: str | None = None, window_days: int = 7):
    """Phase 11.1: decision support page — options, preferred, risk."""
    ds_raw = get_decision_support(scope_type=scope_type, scope_key=scope_key, window_days=window_days, limit=10)
    collab_sug = get_collaboration_action_suggestions(window_days=window_days, limit=10)
    presented_ds = present_decision_support_list(ds_raw.get("items", []))
    presented_sug = present_action_suggestion_list(collab_sug.get("suggestions", []))
    return templates.TemplateResponse(
        request,
        "owner_decision_support.html",
        {
            "scope_type": scope_type,
            "scope_key": scope_key,
            "window_days": window_days,
            "decision_support": presented_ds,
            "collaboration_suggestions": presented_sug},
    )


@app.get("/api/owner/decision-support", dependencies=[Depends(require_owner_key)])
async def api_owner_decision_support(scope_type: str = "portfolio", scope_key: str | None = None, window_days: int = 7):
    """Phase 11.1: JSON decision support."""
    return get_decision_support(scope_type=scope_type, scope_key=scope_key, window_days=window_days, limit=10)


@app.get("/api/owner/action-suggestions", dependencies=[Depends(require_owner_key)])
async def api_owner_action_suggestions(scope: str = "collaboration", scope_key: str | None = None, window_days: int = 7):
    """Phase 11.1: JSON action suggestions (collaboration, project, portfolio, role)."""
    if scope == "project" and scope_key:
        return get_project_action_suggestions(scope_key, window_days=window_days)
    if scope == "portfolio":
        return get_portfolio_action_suggestions(window_days=window_days)
    if scope == "role" and scope_key:
        return get_role_action_suggestions(scope_key, window_days=window_days)
    return get_collaboration_action_suggestions(window_days=window_days)


@app.get("/owner/projects", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_projects_list(request: Request):
    """Phase 9.5: список проектов с health и ссылками на drill-down."""
    raw = list_projects(limit=50)
    projects = present_project_list(raw)
    return templates.TemplateResponse(
        request,
        "owner_projects.html",
        {"projects": projects}
    )


@app.get("/views/owner", dependencies=[Depends(require_owner_key)])
async def view_owner_redirect():
    """Phase 9.7: owner role view — редирект на полный owner dashboard."""
    return RedirectResponse(url="/owner", status_code=302)


@app.get("/views/operator", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def view_operator_page(request: Request):
    """Phase 9.7: operator role-scoped view — runtime, blockers, long-running."""
    raw = get_operator_view()
    view = present_operator_view(raw)
    role_suggestions = None
    try:
        sug = get_role_action_suggestions("operator", window_days=7, limit=3)
        role_suggestions = present_action_suggestion_list(sug.get("suggestions", []))
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "view_operator.html",
        {"view": view, "role_suggestions": role_suggestions}
    )


@app.get("/views/executor", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def view_executor_page(request: Request):
    """Phase 9.7: executor role-scoped view — active tasks, artifacts, blockers."""
    raw = get_executor_view()
    view = present_executor_view(raw)
    role_suggestions = None
    try:
        sug = get_role_action_suggestions("executor", window_days=7, limit=3)
        role_suggestions = present_action_suggestion_list(sug.get("suggestions", []))
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "view_executor.html",
        {"view": view, "role_suggestions": role_suggestions}
    )


@app.get("/views/reviewer", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def view_reviewer_page(request: Request):
    """Phase 9.7: reviewer role-scoped view — pending approvals, decision queue."""
    raw = get_reviewer_view()
    view = present_reviewer_view(raw)
    role_suggestions = None
    try:
        sug = get_role_action_suggestions("reviewer", window_days=7, limit=3)
        role_suggestions = present_action_suggestion_list(sug.get("suggestions", []))
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "view_reviewer.html",
        {"view": view, "role_suggestions": role_suggestions}
    )


# --- Phase 9.8: action center (safe role-aware actions) ---
@app.get("/actions", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def actions_page(request: Request):
    """Phase 9.8: страница доступных действий (owner)."""
    role = "owner"
    actions = list_available_actions(role)
    return templates.TemplateResponse(
        request,
        "actions.html",
        { "actions": actions, "role": role},
    )


@app.post("/actions/run", dependencies=[Depends(require_owner_key)])
async def actions_run(request: Request):
    """Phase 9.8: выполнить действие. Body: action_name (form or JSON). Redirect to /actions?msg=... or return JSON."""
    from fastapi.responses import JSONResponse
    body = {}
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            body = await request.json()
        except Exception:
            pass
    elif "form-urlencoded" in ct or "multipart/form-data" in ct:
        form = await request.form()
        body = dict(form)
    action_name = (body.get("action_name") or request.query_params.get("action_name") or "").strip().lower()
    if not action_name:
        if request.headers.get("accept", "").find("json") >= 0:
            return JSONResponse({"success": False, "error_message": "action_name required"}, status_code=400)
        return RedirectResponse(url="/actions?error=action_name_required", status_code=302)
    role = resolve_and_log("web", {"api_key_valid": True}, actor="web") or "owner"
    if not check_action_access_and_log(role, action_name, actor="web"):
        err = format_access_denied_message(reason="Роль не позволяет выполнить это действие.", action=action_name)
        if request.headers.get("accept", "").find("json") >= 0:
            return JSONResponse(
                {**present_access_denied(reason="role not allowed", action=action_name, role=role), "error_message": err},
                status_code=403,
            )
        return RedirectResponse(url="/actions?error=not_allowed", status_code=302)
    result = execute_action(action_name, role, actor="web")
    if request.headers.get("accept", "").find("json") >= 0:
        return JSONResponse(result)
    from urllib.parse import quote
    msg = "ok" if result.get("success") else "error"
    summary = (result.get("result_summary") or "")[:80]
    return RedirectResponse(url="/actions?msg=%s&summary=%s" % (msg, quote(summary)), status_code=302)


@app.get("/api/actions", dependencies=[Depends(require_owner_key)])
async def api_actions_list():
    """Phase 9.8: JSON список доступных действий (owner)."""
    return {"role": "owner", "actions": list_available_actions("owner")}


# --- Phase 12.2: production readiness ---
@app.get("/owner/readiness", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_readiness_page(request: Request):
    """Phase 12.2: production readiness summary."""
    log_critical_route_access_if_enabled("/owner/readiness", actor="web")
    summary = get_production_readiness_summary()
    card = present_readiness_card(summary)
    owner_text = format_readiness_owner_text(summary)
    return templates.TemplateResponse(
        request,
        "owner_readiness.html",
        { "readiness": card, "owner_text": owner_text},
    )


@app.get("/api/owner/readiness", dependencies=[Depends(require_owner_key)])
async def api_owner_readiness():
    """Phase 12.2: JSON readiness summary."""
    return present_readiness_card(get_production_readiness_summary())


# --- Phase 9.9: domain expertise registry (owner-facing) ---
@app.get("/owner/domains", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_domains_page(request: Request):
    """Phase 9.9: список доменов экспертизы (know_proff registry)."""
    raw = list_domains()
    presented = present_domain_registry_list(raw)
    return templates.TemplateResponse(
        request,
        "owner_domains.html",
        { "domains": presented.get("domains", []), "total": presented.get("total", 0)},
    )


@app.get("/owner/domain/{domain_key}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_domain_detail(request: Request, domain_key: str):
    """Phase 9.9: карточка домена по ключу (или алиасу)."""
    domain = get_domain(domain_key)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    card = present_domain_card(domain)
    profile = present_expert_profile(get_expert_profile(domain_key))
    return templates.TemplateResponse(
        request,
        "owner_domain_detail.html",
        { "domain": card, "profile": profile},
    )


@app.get("/api/owner/domains", dependencies=[Depends(require_owner_key)])
async def api_owner_domains():
    """Phase 9.9: JSON список доменов."""
    raw = list_domains()
    return present_domain_registry_list(raw)


@app.get("/api/owner/domain/{domain_key}", dependencies=[Depends(require_owner_key)])
async def api_owner_domain(domain_key: str):
    """Phase 9.9: JSON карточка домена."""
    domain = get_domain(domain_key)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return present_domain_card(domain)


@app.get("/api/owner/route", dependencies=[Depends(require_owner_key)])
async def api_owner_route(text: str = ""):
    """Phase 9.9: routing demo — подбор домена по тексту задачи (explainable)."""
    suggestions = suggest_domains_for_task(text or "", limit=5)
    return present_routing_result(suggestions, task_preview=text[:200])


# --- Phase 10.5: override/specialization analytics and refinement ---
@app.get("/owner/refinement", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_refinement_page(request: Request, window_days: int = 30):
    """Phase 10.5: Domain & specialization analytics, refinement backlog."""
    override_summary_raw = get_domain_override_summary(window_days)
    override_hotspots_raw = get_override_hotspots(window_days)
    fallback_summary_raw = get_specialization_fallback_summary(window_days)
    spec_hotspots_raw = get_specialization_hotspots(window_days)
    signals_raw = get_refinement_signals(window_days)
    backlog_raw = get_refinement_backlog(window_days)

    override_summary = present_domain_override_summary(override_summary_raw)
    override_hotspots = present_override_hotspots(override_hotspots_raw)
    fallback_summary = present_specialization_fallback_summary(fallback_summary_raw)
    spec_hotspots = present_specialization_hotspots(spec_hotspots_raw)
    signals = present_refinement_signals(signals_raw)
    backlog = present_refinement_backlog(backlog_raw)
    refinement_explanation = None
    try:
        refinement_explanation = present_refinement_explanation(explain_refinement(proposal_id=None, window_days=window_days))
    except Exception:
        pass

    tuning_candidates = None
    tuning_summary = None
    tuning_patch_summary = None
    tuning_outcome_summary = None
    patchable_tuning_preview = None
    manual_tuning_preview = None
    try:
        tun_raw = get_tuning_candidates(window_days=window_days, status="pending_review", limit=5)
        tuning_candidates = present_tuning_candidate_list(tun_raw.get("items", []))
        tuning_summary = present_tuning_summary(get_specialization_tuning_summary(window_days=window_days))
    except Exception:
        pass
    try:
        tuning_patch_summary = present_tuning_patch_summary(get_tuning_patch_summary(window_days=window_days))
        tuning_outcome_summary = present_tuning_outcome_summary(get_tuning_outcome_summary(window_days=window_days))
        pl = list_patchable_tuning_candidates(window_days=window_days, limit=5)
        patchable_tuning_preview = [present_patchable_tuning_candidate(x) for x in pl.get("items", [])]
        ml = list_manual_tuning_candidates(limit=5)
        manual_tuning_preview = [present_patchable_tuning_candidate(x) for x in ml.get("items", [])]
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "owner_refinement.html",
        {
            "window_days": window_days,
            "refinement_explanation": refinement_explanation,
            "tuning_candidates": tuning_candidates,
            "tuning_summary": tuning_summary,
            "tuning_patch_summary": tuning_patch_summary,
            "tuning_outcome_summary": tuning_outcome_summary,
            "patchable_tuning_preview": patchable_tuning_preview,
            "manual_tuning_preview": manual_tuning_preview,
            "override_summary": override_summary,
            "override_hotspots": override_hotspots,
            "fallback_summary": fallback_summary,
            "spec_hotspots": spec_hotspots,
            "signals": signals,
            "backlog": backlog},
    )


@app.get("/api/owner/refinement", dependencies=[Depends(require_owner_key)])
async def api_owner_refinement(window_days: int = 30):
    """Phase 10.5: JSON — override/specialization analytics and refinement backlog."""
    override_summary = get_domain_override_summary(window_days)
    override_hotspots = get_override_hotspots(window_days)
    fallback_summary = get_specialization_fallback_summary(window_days)
    spec_hotspots = get_specialization_hotspots(window_days)
    signals = get_refinement_signals(window_days)
    backlog = get_refinement_backlog(window_days)
    return {
        "window_days": window_days,
        "override_summary": override_summary,
        "override_hotspots": override_hotspots,
        "fallback_summary": fallback_summary,
        "spec_hotspots": spec_hotspots,
        "refinement_signals": signals,
        "refinement_backlog": backlog}


# --- Phase 10.6: refinement proposals workflow ---
@app.get("/owner/refinement/proposals", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_refinement_proposals_page(request: Request, status: str = None):
    """Phase 10.6: список refinement proposals."""
    items = list_refinement_proposals(status=status, limit=50)
    presented = present_refinement_proposal_list(items)
    return templates.TemplateResponse(
        request,
        "owner_refinement_proposals.html",
        { "proposals": presented.get("items", []), "count": presented.get("count", 0), "filter_status": status},
    )


@app.get("/owner/refinement/proposal/{proposal_id}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_refinement_proposal_detail(request: Request, proposal_id: str):
    """Phase 10.6: карточка proposal."""
    p = get_refinement_proposal(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    card = present_refinement_proposal_card(p)
    proposal_explanation = None
    try:
        proposal_explanation = present_refinement_explanation(explain_refinement(proposal_id=proposal_id, window_days=30))
    except Exception:
        pass
    tuning_trace = None
    src = p.get("source_tuning_candidate_id")
    if src:
        try:
            tuning_trace = {
                "candidate_id": src,
                "patchability": present_patchability_card(classify_tuning_candidate_patchability(src)),
                "outcome": present_tuning_outcome(get_tuning_outcome(src) or {})}
        except Exception:
            tuning_trace = {"candidate_id": src, "patchability": {}, "outcome": {}}
    return templates.TemplateResponse(
        request,
        "owner_refinement_proposal_detail.html",
        { "proposal": card, "proposal_explanation": proposal_explanation, "tuning_trace": tuning_trace},
    )


@app.post("/api/owner/refinement/proposals/generate", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposals_generate(window_days: int = 30):
    """Phase 10.6: сгенерировать proposals из backlog."""
    created = generate_refinement_proposals(window_days=window_days)
    return {"created": len(created), "proposals": [present_refinement_proposal_card(c) for c in created]}


@app.get("/api/owner/refinement/proposals", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposals_list(status: str = None, limit: int = 50):
    """Phase 10.6: JSON список proposals."""
    items = list_refinement_proposals(status=status, limit=limit)
    return present_refinement_proposal_list(items)


@app.get("/api/owner/refinement/proposal/{proposal_id}", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposal_get(proposal_id: str):
    """Phase 10.6: JSON карточка proposal."""
    p = get_refinement_proposal(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return present_refinement_proposal_card(p)


# --- Phase 11.2: agent-specific tuning ---
@app.get("/owner/tuning", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_tuning_page(request: Request, window_days: int = 30, status: str = None):
    """Phase 11.2: specialization tuning candidates."""
    tun_raw = get_tuning_candidates(window_days=window_days, status=status, limit=20)
    tun_sum = get_specialization_tuning_summary(window_days=window_days)
    presented = present_tuning_candidate_list(tun_raw.get("items", []))
    patch_sum = None
    patchable_items = []
    manual_items = []
    out_sum = None
    improved_items = []
    worse_items = []
    try:
        patch_sum = present_tuning_patch_summary(get_tuning_patch_summary(window_days=window_days))
        pl = list_patchable_tuning_candidates(window_days=window_days, limit=15)
        patchable_items = [present_patchable_tuning_candidate(x) for x in pl.get("items", [])]
        ml = list_manual_tuning_candidates(limit=15)
        manual_items = [present_patchable_tuning_candidate(x) for x in ml.get("items", [])]
        out_sum = present_tuning_outcome_summary(get_tuning_outcome_summary(window_days=window_days))
        lo = list_tuning_outcomes(window_days=window_days, limit=50).get("items", [])
        improved_items = [present_tuning_outcome(o) for o in lo if o.get("outcome_status") == "improved"][:5]
        worse_items = [present_tuning_outcome(o) for o in lo if o.get("outcome_status") in ("worse", "unchanged")][:5]
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "owner_tuning.html",
        {
            "window_days": window_days,
            "filter_status": status,
            "tuning_candidates": presented,
            "tuning_summary": present_tuning_summary(tun_sum),
            "tuning_patch_summary": patch_sum,
            "patchable_tuning": patchable_items,
            "manual_tuning": manual_items,
            "tuning_outcome_summary": out_sum,
            "improved_outcomes": improved_items,
            "no_improvement_outcomes": worse_items},
    )


@app.get("/owner/tuning/outcomes", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_tuning_outcomes_page(request: Request, window_days: int = 30):
    """Phase 11.3: verified tuning outcomes list."""
    raw = list_tuning_outcomes(window_days=window_days, limit=80)
    items = [present_tuning_outcome(o) for o in raw.get("items", [])]
    summary = present_tuning_outcome_summary(get_tuning_outcome_summary(window_days=window_days))
    cross_layer = None
    try:
        cross_layer = present_cross_layer_synthesis(synthesize_cross_layer_summary(window_days=window_days))
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "owner_tuning_outcomes.html",
        { "window_days": window_days, "outcomes": items, "summary": summary, "cross_layer_synthesis": cross_layer},
    )


@app.get("/api/owner/tuning", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_list(window_days: int = 30, status: str = None, limit: int = 50):
    """Phase 11.2: JSON tuning candidates."""
    return get_tuning_candidates(window_days=window_days, status=status, limit=limit)


@app.get("/api/owner/tuning/summary", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_summary(window_days: int = 30):
    """Phase 11.2: JSON tuning summary."""
    return get_specialization_tuning_summary(window_days=window_days)


@app.get("/api/owner/tuning/patchable", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_patchable(window_days: int = 30, limit: int = 40):
    """Phase 11.3: patchable tuning candidates."""
    raw = list_patchable_tuning_candidates(window_days=window_days, limit=limit)
    return {
        "items": [present_patchable_tuning_candidate(x) for x in raw.get("items", [])],
        "count": raw.get("count", 0),
        "window_days": window_days}


@app.get("/api/owner/tuning/outcomes", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_outcomes(window_days: int = 30, limit: int = 50):
    """Phase 11.3: tuning outcomes list."""
    raw = list_tuning_outcomes(window_days=window_days, limit=limit)
    return {
        "items": [present_tuning_outcome(o) for o in raw.get("items", [])],
        "count": raw.get("count", 0),
        "summary": present_tuning_outcome_summary(get_tuning_outcome_summary(window_days=window_days))}


@app.get("/api/owner/tuning/{candidate_id}/patchability", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_patchability(candidate_id: str):
    """Phase 11.3: patchability classification."""
    return present_patchability_card(classify_tuning_candidate_patchability(candidate_id))


@app.get("/api/owner/tuning/{candidate_id}/outcome", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_outcome_get(candidate_id: str):
    """Phase 11.3: stored tuning outcome."""
    rec = get_tuning_outcome(candidate_id)
    if not rec:
        return present_tuning_outcome({})
    return present_tuning_outcome(rec)


@app.post("/api/owner/tuning/{candidate_id}/evaluate-outcome", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_evaluate_outcome(candidate_id: str, request: Request):
    """Phase 11.3: пересчитать outcome (explainable compare)."""
    body = await request.json() if request.headers.get("content-type", "").find("json") >= 0 else {}
    wd = int(body.get("window_days") or request.query_params.get("window_days") or 30)
    updated = evaluate_tuning_outcome(candidate_id, window_days=wd)
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return present_tuning_outcome(updated)


@app.get("/api/owner/tuning/{candidate_id}/patch-bridge", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_patch_bridge(candidate_id: str):
    """Phase 11.3: candidate → patch candidate (read-only)."""
    return build_patch_from_tuning_candidate(candidate_id)


@app.get("/api/owner/tuning/{candidate_id}", dependencies=[Depends(require_owner_key)])
async def api_owner_tuning_candidate(candidate_id: str):
    """Phase 11.2: JSON один candidate."""
    c = get_tuning_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Tuning candidate not found")
    return present_tuning_candidate_card(c)


@app.post("/api/owner/tuning/proposals/generate", dependencies=[Depends(require_owner_key)])
async def api_tuning_candidates_generate(window_days: int = 30):
    """Phase 11.2: сгенерировать tuning candidates из signals."""
    created = generate_tuning_candidates(window_days=window_days)
    return {"created": len(created), "candidates": [present_tuning_candidate_card(c) for c in created]}


@app.post("/api/owner/tuning/{candidate_id}/review", dependencies=[Depends(require_owner_key)])
async def api_tuning_candidate_review(candidate_id: str, request: Request):
    """Phase 11.2: review candidate — accept/reject."""
    body = await request.json() if request.headers.get("content-type", "").find("json") >= 0 else {}
    if not body:
        body = dict(request.query_params)
    decision = (body.get("decision") or body.get("d") or "").strip().lower()
    notes = body.get("notes") or body.get("note")
    reviewer = body.get("reviewer") or "web"
    updated = mark_tuning_candidate_reviewed(candidate_id, decision=decision, notes=notes, reviewer=reviewer)
    if not updated:
        raise HTTPException(status_code=400, detail="Invalid decision or candidate not found")
    return present_tuning_candidate_card(updated)


@app.post("/api/owner/tuning/{candidate_id}/to-proposal", dependencies=[Depends(require_owner_key)])
async def api_tuning_candidate_to_proposal(candidate_id: str):
    """Phase 11.2: convert candidate to refinement proposal."""
    p = convert_tuning_candidate_to_proposal(candidate_id)
    if not p:
        raise HTTPException(status_code=400, detail="Candidate not accepted or already converted")
    from app.presenters.refinement_proposal_presenters import present_refinement_proposal_card
    return present_refinement_proposal_card(p)


@app.post("/api/owner/tuning/{candidate_id}/verify", dependencies=[Depends(require_owner_key)])
async def api_tuning_candidate_verify(candidate_id: str, request: Request):
    """Phase 11.2: verify outcome — improved/unchanged/worse/insufficient_data."""
    body = await request.json() if request.headers.get("content-type", "").find("json") >= 0 else {}
    if not body:
        body = dict(request.query_params)
    outcome = (body.get("outcome") or body.get("o") or "").strip().lower()
    notes = body.get("notes") or body.get("note")
    updated = mark_tuning_candidate_verified(candidate_id, outcome=outcome, notes=notes)
    if not updated:
        raise HTTPException(status_code=400, detail="Invalid outcome or candidate not found")
    return present_tuning_candidate_card(updated)


@app.post("/api/owner/refinement/proposal/{proposal_id}/review", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposal_review(proposal_id: str, request: Request):
    """Phase 10.6: review — accept или reject. Body: {decision, reviewer?, notes?}."""
    body = await request.json() or {}
    decision = body.get("decision", "").strip()
    reviewer = body.get("reviewer", "web")
    notes = body.get("notes")
    updated = review_refinement_proposal(proposal_id, decision, reviewer=reviewer, notes=notes)
    return present_refinement_review_result(updated)


@app.post("/api/owner/refinement/proposal/{proposal_id}/apply", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposal_apply(proposal_id: str, request: Request):
    """Phase 10.6: отметить как применённое. Body: {reviewer?, notes?}."""
    body = await request.json() or {}
    updated = mark_refinement_proposal_applied(proposal_id, reviewer=body.get("reviewer"), notes=body.get("notes"))
    return present_refinement_review_result(updated) if updated else {"success": False, "message": "Proposal not found or not accepted"}


@app.get("/api/owner/refinement/proposal/{proposal_id}/export", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposal_export(proposal_id: str):
    """Phase 10.6: экспорт patch candidate. Audit: refinement_change_exported."""
    export_data = export_refinement_proposal(proposal_id)
    if not export_data:
        raise HTTPException(status_code=404, detail="Proposal not found or export failed")
    try:
        from app.storage.repositories import get_session_factory, TaskRepository
        from app.shared.audit import log_audit
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, "refinement_change_exported", task_id=None, payload={"proposal_id": proposal_id, "export_format": "refinement_candidate"})
    except Exception:
        pass
    return present_refinement_export(export_data)


# --- Phase 10.7: controlled registry patch application ---
@app.get("/owner/refinement/proposal/{proposal_id}/patch", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_refinement_proposal_patch_page(request: Request, proposal_id: str):
    """Phase 10.7: страница patch — candidate, dry-run, validation, apply."""
    p = get_refinement_proposal(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    patch = build_patch_candidate(proposal_id)
    dry = dry_run_patch(proposal_id) if not patch.get("error") else None
    return templates.TemplateResponse(
        request,
        "owner_refinement_proposal_patch.html",
        { "proposal": present_refinement_proposal_card(p), "patch": present_patch_candidate(patch), "dry_run": present_patch_dry_run(dry) if dry else None},
    )


@app.get("/api/owner/refinement/proposal/{proposal_id}/patch", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposal_patch(proposal_id: str):
    """Phase 10.7: JSON patch candidate (target_file, patch_type, risk, diff_summary, apply_allowed)."""
    patch = build_patch_candidate(proposal_id)
    if patch.get("error"):
        return present_patch_error(patch.get("error"), proposal_id=proposal_id)
    return present_patch_candidate(patch)


@app.post("/api/owner/refinement/proposal/{proposal_id}/patch/dry-run", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposal_patch_dry_run(proposal_id: str):
    """Phase 10.7: dry-run — diff, validation preview, apply_allowed."""
    result = dry_run_patch(proposal_id)
    return present_patch_dry_run(result)


@app.post("/api/owner/refinement/proposal/{proposal_id}/patch/apply", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposal_patch_apply(proposal_id: str, request: Request):
    """Phase 10.7: применить safe patch (backup, write, audit). Body: {actor?}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    actor = (body or {}).get("actor", "web")
    result = apply_patch_candidate(proposal_id, actor=actor)
    return present_patch_apply_result(result)


@app.post("/api/owner/refinement/proposal/{proposal_id}/patch/validate", dependencies=[Depends(require_owner_key)])
async def api_refinement_proposal_patch_validate(proposal_id: str):
    """Phase 10.7: валидация кандидата."""
    result = validate_patch_candidate(proposal_id)
    return present_patch_validation(result)


@app.post("/api/owner/refinement/patch/{patch_id}/rollback", dependencies=[Depends(require_owner_key)])
async def api_refinement_patch_rollback(patch_id: str, request: Request):
    """Phase 10.7: откат по backup_ref (только для зарегистрированных патчей)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    actor = (body or {}).get("actor", "web")
    result = rollback_patch(patch_id, actor=actor)
    return {"success": result.get("success"), "patch_id": patch_id, "error": result.get("error"), "target_file": result.get("target_file")}


@app.get("/owner/project/{project_key}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_project_detail(request: Request, project_key: str, window_days: int = 30):
    """Phase 9.5 / 10.8: drill-down по проекту + domain lifecycle."""
    overview_raw = get_project_overview(project_key)
    health_raw = get_project_health(project_key)
    tasks_raw = get_project_tasks(project_key, limit=20)
    approvals_raw = get_project_pending_approvals(project_key, limit=20)
    artifacts_raw = get_project_recent_artifacts(project_key, limit=20)
    risks_raw = get_project_risks(project_key, limit=10)
    queue_raw = get_project_decision_queue(project_key, limit=10)

    overview = present_project_overview(overview_raw)
    health = present_project_health(health_raw)
    tasks = present_project_tasks(tasks_raw)
    approvals = present_project_approvals(approvals_raw)
    artifacts = present_project_artifacts(artifacts_raw)
    risks = present_project_risks(risks_raw)
    decision_queue = present_project_decision_queue(queue_raw)

    lifecycle_presented = None
    evolution_refinement = None
    try:
        from app.services.project_domain_lifecycle import get_project_domain_lifecycle
        from app.presenters.project_domain_lifecycle_presenters import present_project_domain_lifecycle
        lifecycle_raw = get_project_domain_lifecycle(project_key, window_days=window_days)
        lifecycle_presented = present_project_domain_lifecycle(lifecycle_raw)
    except Exception:
        pass
    try:
        from app.services.project_domain_evolution_refinement import get_project_domain_evolution_refinement
        from app.presenters.project_domain_evolution_presenters import present_evolution_refinement
        ev_raw = get_project_domain_evolution_refinement(project_key, window_days=window_days)
        evolution_refinement = present_evolution_refinement(ev_raw)
    except Exception:
        pass

    project_handoffs = present_project_handoff_signals(get_project_handoff_signals(project_key))
    project_explanation = None
    try:
        project_explanation = present_project_explanation(explain_project(project_key, window_days=window_days))
    except Exception:
        pass

    project_suggestions = None
    try:
        sug_raw = get_project_action_suggestions(project_key, window_days=window_days, limit=3)
        project_suggestions = present_action_suggestion_list(sug_raw.get("suggestions", []))
    except Exception:
        pass

    project_collab_executions = None
    project_collab_outcomes = None
    try:
        from app.services.collaboration_execution_store import list_executions
        subj = [x for x in list_executions(limit=80) if x.get("subject_type") == "project" and str(x.get("subject_key")) == str(project_key)]
        subj.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        project_collab_executions = present_collaboration_execution_list(subj[:10])
        out_cards = []
        for x in subj[:12]:
            if (x.get("execution_status") or "") != "closed":
                continue
            eid = x.get("execution_id")
            if not eid:
                continue
            oc = get_collaboration_execution_outcome(eid)
            if oc:
                out_cards.append(present_collaboration_outcome_card(oc))
        if out_cards:
            project_collab_outcomes = {"items": out_cards}
    except Exception:
        pass

    project_intervention = None
    try:
        bundle = get_intervention_bundle("project", scope_key=project_key, window_days=window_days)
        project_intervention = present_intervention_bundle(bundle)
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "owner_project_detail.html",
        {
            "project_key": project_key,
            "overview": overview,
            "health": health,
            "tasks": tasks,
            "approvals": approvals,
            "artifacts": artifacts,
            "risks": risks,
            "decision_queue": decision_queue,
            "lifecycle": lifecycle_presented,
            "evolution_refinement": evolution_refinement,
            "collaboration": project_handoffs,
            "project_explanation": project_explanation,
            "project_suggestions": project_suggestions,
            "project_collab_executions": project_collab_executions,
            "project_collab_outcomes": project_collab_outcomes,
            "project_intervention": project_intervention},
    )


@app.get("/api/owner/project/{project_key}/lifecycle", dependencies=[Depends(require_owner_key)])
async def api_owner_project_lifecycle(project_key: str, window_days: int = 30):
    """Phase 10.8: JSON lifecycle по проекту."""
    from app.services.project_domain_lifecycle import get_project_domain_lifecycle
    from app.presenters.project_domain_lifecycle_presenters import present_project_domain_lifecycle
    raw = get_project_domain_lifecycle(project_key, window_days=window_days)
    return present_project_domain_lifecycle(raw)


@app.get("/api/owner/domain-lifecycle", dependencies=[Depends(require_owner_key)])
async def api_owner_domain_lifecycle(window_days: int = 30):
    """Phase 10.8: JSON сводка domain lifecycle (дрифт, нестабильные, diversification)."""
    from app.services.project_domain_lifecycle import get_cross_project_domain_lifecycle_summary
    from app.presenters.project_domain_lifecycle_presenters import present_cross_project_domain_lifecycle_summary
    raw = get_cross_project_domain_lifecycle_summary(window_days=window_days)
    return present_cross_project_domain_lifecycle_summary(raw)


@app.get("/api/owner/project/{project_key}/evolution-refinement", dependencies=[Depends(require_owner_key)])
async def api_owner_project_evolution_refinement(project_key: str, window_days: int = 30):
    """Phase 11.9: JSON evolution refinement по проекту."""
    from app.services.project_domain_evolution_refinement import get_project_domain_evolution_refinement
    from app.presenters.project_domain_evolution_presenters import present_evolution_refinement
    raw = get_project_domain_evolution_refinement(project_key, window_days=window_days)
    return present_evolution_refinement(raw)


@app.get("/api/owner/domain-evolution-summary", dependencies=[Depends(require_owner_key)])
async def api_owner_domain_evolution_summary(window_days: int = 30):
    """Phase 11.9: JSON сводка domain evolution (attention items, drift, diversification)."""
    from app.services.project_domain_evolution_refinement import get_project_domain_transition_summary
    from app.presenters.project_domain_evolution_presenters import present_attention_items
    raw = get_project_domain_transition_summary(window_days=window_days)
    return {
        "window_days": raw.get("window_days"),
        "attention_items_count": raw.get("attention_items_count", 0),
        "drift_requiring_intervention_count": raw.get("drift_requiring_intervention_count", 0),
        "diversification_requiring_review_count": raw.get("diversification_requiring_review_count", 0),
        "attention_items": present_attention_items(raw.get("attention_items", [])).get("items", [])}


@app.get("/tasks", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def list_tasks(request: Request):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
        items = [
            {
                "id": t.id,
                "domain": t.domain or "-",
                "status": t.status,
                "criticality": t.criticality or "-",
                "created_at": t.created_at.isoformat() if t.created_at else "-"}
            for t in tasks
        ]
    return templates.TemplateResponse(
        request,
        "tasks.html",
        {"tasks": items}
    )


@app.get("/tasks/{task_id}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def task_detail(request: Request, task_id: int, raw: int = 0):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # HF-2: redaction. raw=1 + ALLOW_PII в тексте → PII можно, но scrub_secrets всегда
        owner_text_raw = task.owner_text or ""
        allow_pii = "ALLOW_PII" in owner_text_raw
        if raw == 1 and allow_pii:
            owner_text_display = scrub_secrets(owner_text_raw)
        else:
            owner_text_display = redact(owner_text_raw)

        summary_display = redact(task.summary or "")

        timeline = []
        if task.created_at:
            timeline.append({"status": "NEW", "at": task.created_at, "note": "Created"})
        if task.updated_at and task.status != "NEW":
            timeline.append({"status": task.status, "at": task.updated_at, "note": f"Status: {task.status}"})

        decisions = [{"decision": d.decision, "rationale": redact(d.rationale or ""), "owner_approval": d.owner_approval, "at": d.created_at} for d in task.decisions]
        handoffs = [
            {"id": h.id, "step": h.step_name, "md_path": h.md_path}
            for h in sorted(task.handoffs, key=lambda x: x.step_index)
        ]

        # Phase 10.0: domain metadata for expertise hint
        try:
            from app.services.task_domain_store import get_task_domain_metadata
            domain_metadata = get_task_domain_metadata(task_id)
        except Exception:
            domain_metadata = None
        # Phase 10.1: effective domain context (override-aware)
        try:
            from app.services.workflow_domain_context import get_effective_domain_context
            effective_domain_context = get_effective_domain_context(task_id, task.owner_text)
        except Exception:
            effective_domain_context = None
        # Phase 10.2: step-specific hint and list of domains for override UX
        domain_prompt_step_hint = None
        domain_keys_for_override = []
        if effective_domain_context and effective_domain_context.get("selected_primary_domain"):
            try:
                from app.services.domain_prompt_profiles import build_pipeline_domain_prompt, build_court_domain_prompt
                pp = build_pipeline_domain_prompt(task_id, task.owner_text)
                cp = build_court_domain_prompt(task_id, task.owner_text)
                domain_prompt_step_hint = {
                    "pipeline_focus": pp.get("step_specific_focus"),
                    "court_focus": cp.get("step_specific_focus")}
            except Exception:
                pass
            try:
                from app.services.domain_registry import list_domains
                domain_keys_for_override = [d.get("domain_key") for d in list_domains() if d.get("domain_key")]
            except Exception:
                pass

        query_suffix = ("?" + request.url.query) if request.url.query else ""

        task_explanation = None
        try:
            task_explanation = present_task_explanation(explain_task(task_id))
        except Exception:
            pass

        return templates.TemplateResponse(
            request,
        "task_detail.html",
            {
                "task": task,
                "owner_text_display": owner_text_display,
                "summary_display": summary_display,
                "timeline": timeline,
                "decisions": decisions,
                "handoffs": handoffs,
                "domain_metadata": domain_metadata,
                "effective_domain_context": effective_domain_context,
                "domain_prompt_step_hint": domain_prompt_step_hint,
                "domain_keys_for_override": domain_keys_for_override,
                "query_suffix": query_suffix,
                "task_explanation": task_explanation},
        )


@app.get("/tasks/{task_id}/artifacts/{handoff_id}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def task_artifact_detail(request: Request, task_id: int, handoff_id: int):
    """Просмотр содержимого artifact (handoff md)."""
    from app.storage.repositories import TaskRepository
    from app.storage.models import Handoff

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        handoff = next((h for h in task.handoffs if h.id == handoff_id), None)
        if not handoff or not handoff.md_path:
            raise HTTPException(status_code=404, detail="Artifact not found")

        path = Path(handoff.md_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Artifact file not found")

        content = path.read_text(encoding="utf-8")

        # Минимальная HTML-страница под тест.
        html = f"""
<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Artifact {handoff_id}</title></head>
<body>
<h1>Artifact {handoff_id}</h1>
<pre>{content}</pre>
</body>
</html>
"""
        return HTMLResponse(content=html)


@app.post("/tasks/{task_id}/approve", dependencies=[Depends(require_owner_key)])
async def task_approve(task_id: int):
    """API/UI: approve (POST) переводит DONE и редиректит обратно."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        repo.update_task(task_id, status="DONE")
    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@app.post("/tasks/{task_id}/merged", dependencies=[Depends(require_owner_key)])
async def task_merged(task_id: int):
    """API/UI: merged (POST) переводит DONE и редиректит обратно."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        repo.update_task(task_id, status="DONE")
    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@app.post("/tasks/{task_id}/set-domain", response_class=RedirectResponse, dependencies=[Depends(require_owner_key)])
async def task_set_domain(request: Request, task_id: int):
    """Phase 10.2: форма — установить override домена. Redirect обратно на task detail."""
    form = await request.form()
    domain_key = (form.get("domain_key") or "").strip()
    reason = (form.get("reason") or "").strip() or None
    if not domain_key:
        raise HTTPException(status_code=400, detail="domain_key required")
    try:
        from app.services.workflow_domain_context import apply_domain_override
        result = apply_domain_override(task_id, domain_key, reason=reason, actor="owner", source="web")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Unknown domain"))
    from app.shared.audit import log_audit
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        log_audit(repo, "domain_override", task_id=task_id, payload={"new_primary_domain": domain_key, "actor": "owner", "source": "web"})
    query_suffix = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(url=f"/tasks/{task_id}{query_suffix}", status_code=303)


@app.post("/tasks/{task_id}/clear-domain", response_class=RedirectResponse, dependencies=[Depends(require_owner_key)])
async def task_clear_domain(request: Request, task_id: int):
    """Phase 10.2: форма — снять override. Redirect обратно на task detail."""
    try:
        from app.services.domain_override_store import clear_override, get_override
        had = get_override(task_id)
        cleared = clear_override(task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if cleared:
        from app.shared.audit import log_audit
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, "domain_override_cleared", task_id=task_id, payload={"previous_primary_domain": had.get("new_primary_domain") if had else None, "actor": "owner", "source": "web"})
    query_suffix = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(url=f"/tasks/{task_id}{query_suffix}", status_code=303)


@app.middleware("http")
async def audit_api_middleware(request: Request, call_next):
    """Audit для /api/* запросов."""
    start = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        latency_ms = int((time.perf_counter() - start) * 1000)
        task_id = None
        parts = path.strip("/").split("/")
        if "tasks" in parts:
            try:
                idx = parts.index("tasks")
                if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                    task_id = int(parts[idx + 1])
            except (ValueError, IndexError):
                pass
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            payload = {"actor": "owner", "route": path, "task_id": task_id, "status_code": response.status_code, "latency_ms": latency_ms}
            req_id = request.headers.get("X-Request-Id")
            if req_id:
                payload["request_id"] = req_id
            repo.add_audit_event(event_type="api_request", task_id=task_id, payload=payload)
    return response


def run_dashboard():
    import uvicorn
    from app.shared.auth import require_owner_key_at_startup
    require_owner_key_at_startup()
    cfg = get_dashboard_config()
    host = cfg.get("host", "0.0.0.0")
    port = int(cfg.get("port", os.getenv("DASHBOARD_PORT", "8080")))
    uvicorn.run(app, host=host, port=port)
