# app/dashboard/api/intake.py — /intake/*, /owner/overrides, /exploration/select routes.

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.dashboard.api.common import (
    ExplorationSelectBody,
    NormalizeIntakeRequest,
    OwnerOverrideBody,
    get_session_factory,
    log_audit,
    normalize_intake,
    response_to_public_dict,
    run_task_orchestration,
    TaskRepository,
)

router = APIRouter()


@router.post("/intake/normalize")
async def api_intake_normalize(body: NormalizeIntakeRequest):
    """Нормализация входа (Smart Intake v0/v1): без создания задачи. Требует X-API-Key."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        resp = normalize_intake(body, repo=repo)
    return response_to_public_dict(resp)


@router.post("/owner/overrides")
async def api_post_owner_override(body: OwnerOverrideBody):
    """Разовое переопределение правила владельца (Owner Memory)."""
    vu = None
    if body.valid_until:
        try:
            vu = datetime.fromisoformat(body.valid_until.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid valid_until: {exc}") from exc
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        row = repo.add_owner_override(
            owner_key="default",
            target_scope=body.target_scope,
            target_id=body.target_id,
            override_text=body.override_text.strip(),
            valid_until=vu,
        )
        log_audit(
            repo,
            "owner_override_created",
            payload={"override_id": row.id, "target_scope": body.target_scope, "target_id": body.target_id},
        )
    return {"id": row.id, "owner_key": "default"}


@router.post("/exploration/select")
async def api_select_exploration_option(body: ExplorationSelectBody):
    """
    API fallback выбора сценария exploration (аналог Telegram callback sc:{task_id}:{option_id}).
    После выбора автоматически запускает orchestration.
    """
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(body.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        ba = dict(task.business_action_json or {})
        exploration = dict(ba.get("exploration") or {})
        if not exploration.get("exploration_mode"):
            raise HTTPException(status_code=409, detail="Task is not in exploration mode")
        options = exploration.get("options") if isinstance(exploration.get("options"), list) else []
        valid_ids = {str(o.get("id")) for o in options if isinstance(o, dict) and o.get("id")}
        if body.option_id not in valid_ids:
            raise HTTPException(status_code=400, detail="Unknown exploration option_id")
        exploration["selected_option_id"] = body.option_id
        ba["exploration"] = exploration
        repo.update_task(body.task_id, business_action_json=ba, status="TRIAGED")
        log_audit(
            repo,
            "exploration_option_selected",
            task_id=body.task_id,
            payload={"option_id": body.option_id, "source": "api"},
        )
        result = run_task_orchestration(repo, body.task_id, source="api_exploration_select")
        updated = repo.get_task(body.task_id)
        return {
            "id": body.task_id,
            "status": updated.status if updated else (result or {}).get("status"),
            "domain": updated.domain if updated else None,
            "task_type": updated.task_type if updated else None,
            "selected_option_id": body.option_id,
            "result": result,
        }
