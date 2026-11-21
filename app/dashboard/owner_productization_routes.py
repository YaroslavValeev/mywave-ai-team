"""Owner productization — Phase 9.4 dashboard only (safe incremental mount).

Do not dump all nested /owner* routes here; expand page-by-page in follow-up PRs.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
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
