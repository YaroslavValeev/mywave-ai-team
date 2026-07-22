# app/dashboard/api/business.py — /business/* routes.

from fastapi import APIRouter

from app.dashboard.api.common import (
    _get_cached_business_payload,
    get_session_factory,
    TaskRepository,
)

router = APIRouter()


@router.get("/business/metrics")
async def api_business_metrics():
    """Базовые бизнес-метрики v1 для Owner Console."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        projects = repo.list_active_projects(limit=200)
        metrics_payload, _, _ = _get_cached_business_payload(repo)

        return {
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "project_type": getattr(p, "project_type", None),
                    "stage": getattr(p, "stage", None),
                    "owner_focus_level": getattr(p, "owner_focus_level", None),
                }
                for p in projects
            ],
            **metrics_payload,
        }


@router.get("/business/growth/insight")
async def api_business_growth_insight():
    """Temporal + anti-noise: топы по 7d/30d, тренды, рекомендации."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        _, growth_payload, _ = _get_cached_business_payload(repo)
        return growth_payload
