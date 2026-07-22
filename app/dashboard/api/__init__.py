# app/dashboard/api/__init__.py — assemble sub-routers into the unified API router.

from fastapi import APIRouter, Depends

from app.shared.auth import require_owner_key

from app.dashboard.api import business, events, gateway, intake, system, tasks
from app.dashboard.api.common import apply_merge_confirmation, apply_owner_decision

router = APIRouter(prefix="/api", tags=["api"], dependencies=[Depends(require_owner_key)])

router.include_router(system.router)
router.include_router(business.router)
router.include_router(gateway.router)
router.include_router(events.router)
router.include_router(intake.router)
router.include_router(tasks.router)

__all__ = ["router", "apply_owner_decision", "apply_merge_confirmation"]
