"""Owner productization routes — Phase 9.4–9.6 + 9.9 + readiness/effectiveness (A3).

Mounted into live dashboard without replacing mission/runtime UI.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.shared.auth import require_owner_key
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
    get_project_risks,
    get_project_decision_queue,
    get_project_tasks,
    get_project_pending_approvals,
    get_project_recent_artifacts,
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

router = APIRouter(tags=["owner-productization"])
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/owner", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_dashboard(request: Request):
    """Phase 9.4: read-only owner dashboard."""
    overview = present_dashboard_overview(get_dashboard_overview())
    next_actions = present_dashboard_next_actions(get_dashboard_next_actions(limit=5))
    blockers = present_dashboard_blockers(get_dashboard_blockers(limit=10))
    decision_queue = present_dashboard_decision_queue(get_dashboard_decision_queue(limit=10))
    project_health = present_dashboard_project_health(get_dashboard_project_health(limit=10))
    recent_artifacts = present_dashboard_recent_artifacts(get_dashboard_recent_artifacts(limit=10))
    digest_preview = present_dashboard_digest_preview(get_dashboard_digest_preview())

    collaboration_hotspots = None
    try:
        from app.services.collaboration_outcomes import get_collaboration_hotspots
        from app.presenters.collaboration_presenters import present_collaboration_hotspots

        collaboration_hotspots = present_collaboration_hotspots(
            get_collaboration_hotspots(window_days=7, limit=5)
        )
    except Exception:
        pass

    cross_layer_synthesis = None
    try:
        from app.services.cross_layer_effectiveness import synthesize_cross_layer_summary
        from app.presenters.cross_layer_effectiveness_presenters import present_cross_layer_synthesis

        cross_layer_synthesis = present_cross_layer_synthesis(
            synthesize_cross_layer_summary(window_days=30)
        )
    except Exception:
        pass

    readiness = None
    try:
        from app.services.production_readiness import get_production_readiness_summary
        from app.presenters.production_readiness_presenters import present_readiness_card

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
            "cross_layer_synthesis": cross_layer_synthesis,
        },
    )


@router.get("/owner/projects", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_projects_list(request: Request):
    """Phase 9.5: project list."""
    projects = SimpleNamespace(**present_project_list(list_projects(limit=50)))
    return templates.TemplateResponse(request, "owner_projects.html", {"projects": projects})


@router.get("/owner/project/{project_key}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_project_detail(request: Request, project_key: str, window_days: int = 30):
    """Phase 9.5: project drill-down (core fields; extras optional)."""
    overview = present_project_overview(get_project_overview(project_key))
    health = present_project_health(get_project_health(project_key))
    tasks = present_project_tasks(get_project_tasks(project_key, limit=20))
    approvals = present_project_approvals(get_project_pending_approvals(project_key, limit=20))
    artifacts = present_project_artifacts(get_project_recent_artifacts(project_key, limit=20))
    risks = present_project_risks(get_project_risks(project_key, limit=10))
    decision_queue = present_project_decision_queue(get_project_decision_queue(project_key, limit=10))

    ctx = {
        "overview": overview,
        "health": health,
        "tasks": tasks,
        "approvals": approvals,
        "artifacts": artifacts,
        "risks": risks,
        "decision_queue": decision_queue,
        "lifecycle_presented": None,
        "evolution_refinement": None,
        "project_handoffs": None,
        "project_explanation": None,
        "project_suggestions": None,
        "project_collab_executions": None,
        "project_collab_outcomes": None,
        "project_intervention": None,
        "window_days": window_days,
    }
    try:
        from app.services.project_domain_lifecycle import get_project_domain_lifecycle
        from app.presenters.project_domain_lifecycle_presenters import present_project_domain_lifecycle

        ctx["lifecycle_presented"] = present_project_domain_lifecycle(
            get_project_domain_lifecycle(project_key, window_days=window_days)
        )
    except Exception:
        pass
    return templates.TemplateResponse(request, "owner_project_detail.html", ctx)


@router.get("/owner/portfolio", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_portfolio_page(request: Request, window_days: int = 30):
    """Phase 9.6: portfolio view (core + safe optional blocks)."""
    overview = present_portfolio_overview(get_portfolio_overview())
    top_problem = present_top_problem_projects(get_top_problem_projects(limit=10))
    backlog = present_approvals_backlog_by_project(get_approvals_backlog_by_project(limit=15))
    rework = present_rework_hotspots(get_rework_hotspots(limit=10))
    degraded = present_degraded_hotspots(get_degraded_hotspots(limit=10))
    focus = present_portfolio_focus_list(get_portfolio_focus_list(limit=5))
    digest = present_portfolio_digest(get_portfolio_digest(window_days=7))

    ctx = {
        "overview": overview,
        "top_problem": top_problem,
        "backlog": backlog,
        "rework": rework,
        "degraded": degraded,
        "focus": focus,
        "digest": digest,
        "lifecycle_summary": None,
        "evolution_transition_summary": None,
        "collaboration_hotspots": None,
        "portfolio_explanation": None,
        "portfolio_decision_support": None,
        "portfolio_collab_executions": None,
        "portfolio_collab_outcome_summary": None,
        "portfolio_cross_layer_synthesis": None,
        "portfolio_intervention_plans": None,
        "portfolio_cross_layer_bundle": None,
        "window_days": window_days,
    }
    try:
        from app.services.collaboration_outcomes import get_collaboration_hotspots
        from app.presenters.collaboration_presenters import present_collaboration_hotspots

        ctx["collaboration_hotspots"] = present_collaboration_hotspots(
            get_collaboration_hotspots(window_days=window_days, limit=10)
        )
    except Exception:
        pass
    return templates.TemplateResponse(request, "owner_portfolio.html", ctx)


@router.get("/views/owner", dependencies=[Depends(require_owner_key)])
async def view_owner_redirect():
    return RedirectResponse(url="/owner", status_code=302)


@router.get("/owner/domains", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_domains_page(request: Request):
    from app.services.domain_registry import list_domains
    from app.presenters.domain_presenters import present_domain_registry_list

    presented = present_domain_registry_list(list_domains())
    return templates.TemplateResponse(
        request,
        "owner_domains.html",
        {"domains": presented.get("domains", []), "total": presented.get("total", 0)},
    )


@router.get("/owner/domain/{domain_key}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_domain_detail(request: Request, domain_key: str):
    from app.services.domain_registry import get_domain, get_expert_profile
    from app.presenters.domain_presenters import present_domain_card, present_expert_profile

    domain = get_domain(domain_key)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return templates.TemplateResponse(
        request,
        "owner_domain_detail.html",
        {
            "domain": present_domain_card(domain),
            "profile": present_expert_profile(get_expert_profile(domain_key)),
        },
    )


@router.get("/api/owner/domains", dependencies=[Depends(require_owner_key)])
async def api_owner_domains():
    from app.services.domain_registry import list_domains
    from app.presenters.domain_presenters import present_domain_registry_list

    return present_domain_registry_list(list_domains())


@router.get("/api/owner/domain/{domain_key}", dependencies=[Depends(require_owner_key)])
async def api_owner_domain(domain_key: str):
    from app.services.domain_registry import get_domain
    from app.presenters.domain_presenters import present_domain_card

    domain = get_domain(domain_key)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return present_domain_card(domain)


@router.get("/api/owner/route", dependencies=[Depends(require_owner_key)])
async def api_owner_route(text: str = ""):
    from app.services.expert_routing import suggest_domains_for_task
    from app.presenters.domain_presenters import present_routing_result

    suggestions = suggest_domains_for_task(text or "", limit=5)
    return present_routing_result(suggestions, task_preview=(text or "")[:200])


@router.get("/owner/effectiveness", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_effectiveness_page(request: Request, window_days: int = 30):
    from app.services.cross_layer_effectiveness import synthesize_cross_layer_summary
    from app.presenters.cross_layer_effectiveness_presenters import present_cross_layer_synthesis

    raw = synthesize_cross_layer_summary(window_days=window_days)
    return templates.TemplateResponse(
        request,
        "owner_effectiveness.html",
        {"synthesis": present_cross_layer_synthesis(raw)},
    )


@router.get("/owner/readiness", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def owner_readiness_page(request: Request):
    from app.services.production_readiness import get_production_readiness_summary
    from app.presenters.production_readiness_presenters import (
        present_readiness_card,
        format_readiness_owner_text,
    )

    try:
        from app.services.role_access import log_critical_route_access_if_enabled

        log_critical_route_access_if_enabled("/owner/readiness", actor="web")
    except Exception:
        pass
    summary = get_production_readiness_summary()
    return templates.TemplateResponse(
        request,
        "owner_readiness.html",
        {
            "readiness": present_readiness_card(summary),
            "owner_text": format_readiness_owner_text(summary),
        },
    )


@router.get("/api/owner/readiness", dependencies=[Depends(require_owner_key)])
async def api_owner_readiness():
    from app.services.production_readiness import get_production_readiness_summary
    from app.presenters.production_readiness_presenters import present_readiness_card

    return present_readiness_card(get_production_readiness_summary())
