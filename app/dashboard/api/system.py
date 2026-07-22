# app/dashboard/api/system.py — /system/* routes.

from fastapi import APIRouter

from app.dashboard.api.common import (
    _get_cached_business_payload,
    classify_owner_day_status,
    collect_system_health,
    get_session_factory,
    owner_daily_checklist_bullets,
    TaskRepository,
)

router = APIRouter()


@router.get("/system/health")
async def api_system_health():
    """Сводный статус интеграций и runtime-конфигурации."""
    return collect_system_health()


@router.get("/system/data_health")
async def api_system_data_health():
    """Минимальный health-check данных для production readiness."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        metrics_payload, _, data_health_payload = _get_cached_business_payload(repo)
        growth_insight = metrics_payload.get("growth_insight") if isinstance(metrics_payload, dict) else {}
        day_status = classify_owner_day_status(data_health_payload, growth_insight if isinstance(growth_insight, dict) else None)
        return {
            **data_health_payload,
            "owner_protocol": {
                "day_status": day_status,
                "checklist": owner_daily_checklist_bullets(),
            },
        }
