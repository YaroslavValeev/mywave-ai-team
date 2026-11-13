# Domain / specialization productization routes (Phase 10.2 / 10.4) — ported from nested api_router.

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dashboard.api.common import get_session_factory, require_owner_key, TaskRepository
from app.shared.audit import log_audit

router = APIRouter()


@router.get("/tasks/{task_id}/specialization-context")
async def api_get_task_specialization_context(task_id: int, _=Depends(require_owner_key)):
    """Phase 10.4: effective domain + per-step specialization, explainability, fallback flags."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    try:
        from app.services.agent_specializations import suggest_specialization

        pipeline_sel = suggest_specialization(task_id, "pipeline", getattr(task, "owner_text", None))
        roundtable_sel = suggest_specialization(task_id, "roundtable", getattr(task, "owner_text", None))
        court_sel = suggest_specialization(task_id, "court", getattr(task, "owner_text", None))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Specialization error: {e!s}")
    return {
        "task_id": task_id,
        "effective_domain": pipeline_sel.get("effective_domain"),
        "per_step": {
            "pipeline": {
                "selected_specialization": pipeline_sel.get("selected_specialization", {}).get(
                    "specialization_key"
                ),
                "profile_name": pipeline_sel.get("profile_name"),
                "expected_output_type": pipeline_sel.get("expected_output_type"),
                "fallback_used": pipeline_sel.get("fallback_used", False),
                "reason": pipeline_sel.get("selection_reason"),
            },
            "roundtable": {
                "selected_specialization": roundtable_sel.get("selected_specialization", {}).get(
                    "specialization_key"
                ),
                "profile_name": roundtable_sel.get("profile_name"),
                "expected_output_type": roundtable_sel.get("expected_output_type"),
                "fallback_used": roundtable_sel.get("fallback_used", False),
                "reason": roundtable_sel.get("selection_reason"),
            },
            "court": {
                "selected_specialization": court_sel.get("selected_specialization", {}).get(
                    "specialization_key"
                ),
                "profile_name": court_sel.get("profile_name"),
                "expected_output_type": court_sel.get("expected_output_type"),
                "fallback_used": court_sel.get("fallback_used", False),
                "reason": court_sel.get("selection_reason"),
            },
        },
        "explainability": {
            "pipeline_reason": pipeline_sel.get("selection_reason"),
            "roundtable_reason": roundtable_sel.get("selection_reason"),
            "court_reason": court_sel.get("selection_reason"),
        },
        "fallback_used_any": (
            pipeline_sel.get("fallback_used")
            or roundtable_sel.get("fallback_used")
            or court_sel.get("fallback_used")
        ),
    }


@router.get("/tasks/{task_id}/domain-context")
async def api_get_task_domain_context(task_id: int, _=Depends(require_owner_key)):
    """Phase 10.2: debug — effective domain context и step-specific prompt profiles."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
        from app.services.domain_prompt_profiles import (
            build_pipeline_domain_prompt,
            build_roundtable_domain_prompt,
            build_court_domain_prompt,
        )

        effective = get_effective_domain_context(task_id, getattr(task, "owner_text", None))
        pipeline_profile = build_pipeline_domain_prompt(task_id, getattr(task, "owner_text", None))
        roundtable_profile = build_roundtable_domain_prompt(
            task_id, getattr(task, "owner_text", None)
        )
        court_profile = build_court_domain_prompt(task_id, getattr(task, "owner_text", None))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Domain context error: {e!s}")
    return {
        "task_id": task_id,
        "effective_domain_context": effective,
        "override_status": {
            "active": effective.get("domain_override", False),
            "reason": effective.get("domain_override_reason"),
            "source": effective.get("domain_override_source"),
        },
        "step_profiles": {
            "pipeline": {
                **{k: v for k, v in pipeline_profile.items() if k != "compact_context"},
                "compact_context_length": len(pipeline_profile.get("compact_context") or ""),
            },
            "roundtable": {
                **{k: v for k, v in roundtable_profile.items() if k != "compact_context"},
                "compact_context_length": len(roundtable_profile.get("compact_context") or ""),
            },
            "court": {
                **{k: v for k, v in court_profile.items() if k != "compact_context"},
                "compact_context_length": len(court_profile.get("compact_context") or ""),
            },
        },
        "explainability": {
            "pipeline_focus": pipeline_profile.get("step_specific_focus"),
            "roundtable_focus": roundtable_profile.get("step_specific_focus"),
            "court_focus": court_profile.get("step_specific_focus"),
        },
    }


@router.post("/tasks/{task_id}/domain-override")
async def api_set_domain_override(task_id: int, request: Request, _=Depends(require_owner_key)):
    """Phase 10.2: установить override домена для задачи. Body: {domain_key, reason?}."""
    body = await request.json() or {}
    domain_key = (body.get("domain_key") or "").strip()
    if not domain_key:
        raise HTTPException(status_code=400, detail="domain_key required")
    try:
        from app.services.workflow_domain_context import apply_domain_override

        result = apply_domain_override(
            task_id, domain_key, reason=body.get("reason"), actor="owner", source="web"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Override error: {e!s}")
    if not result.get("success"):
        raise HTTPException(
            status_code=400, detail=result.get("message", result.get("error", "Unknown domain"))
        )
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        log_audit(
            repo,
            "domain_override",
            task_id=task_id,
            payload={"new_primary_domain": domain_key, "actor": "owner", "source": "web"},
        )
    return {"task_id": task_id, "override": result.get("override"), "message": "Override set"}


@router.post("/tasks/{task_id}/domain-override/clear")
async def api_clear_domain_override(task_id: int, _=Depends(require_owner_key)):
    """Phase 10.2: снять override домена."""
    try:
        from app.services.domain_override_store import clear_override, get_override

        had = get_override(task_id)
        cleared = clear_override(task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear error: {e!s}")
    if not cleared:
        return {"task_id": task_id, "cleared": False, "message": "No active override"}
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        log_audit(
            repo,
            "domain_override_cleared",
            task_id=task_id,
            payload={
                "previous_primary_domain": had.get("new_primary_domain") if had else None,
                "actor": "owner",
                "source": "web",
            },
        )
    return {"task_id": task_id, "cleared": True, "message": "Override cleared"}
