# app/dashboard/api/gateway.py — /gateway/* routes.

from fastapi import APIRouter, HTTPException, Request

from app.dashboard.api.common import (
    get_session_factory,
    TaskRepository,
)

router = APIRouter()


@router.get("/gateway/catalog")
async def api_gateway_catalog():
    """OpenClaw-style каталог capabilities без секретов."""
    from app.gateway import gateway_catalog

    return {"model": "gateway-v1", "capabilities": gateway_catalog()}


@router.post("/gateway/evaluate")
async def api_gateway_evaluate(request: Request):
    """
    Проверить пару scope/action. Секрет в ответ не включается.
    Body: { "scope": "github", "action": "pr", "task_id": optional }.
    """
    from app.gateway import evaluate_capability

    body = await request.json() or {}
    scope = str(body.get("scope") or "")
    action = str(body.get("action") or "")
    task_id = body.get("task_id")
    tid: int | None = None
    audit_repo = None
    if task_id is not None:
        try:
            tid = int(task_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="task_id must be int") from None
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            if not repo.get_task(tid):
                raise HTTPException(status_code=404, detail="Task not found")
            r = evaluate_capability(scope, action, task_id=tid, audit_repo=repo)
    else:
        r = evaluate_capability(scope, action)

    return {
        "ok": r.ok,
        "scope": r.scope,
        "action": r.action,
        "runtime": r.runtime,
        "server_resolvable": r.server_resolvable,
        "message": r.message,
        "secret_configured": r.ok,
    }
