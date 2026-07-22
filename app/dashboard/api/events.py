# app/dashboard/api/events.py — /events, /audit routes.

from fastapi import APIRouter, HTTPException, Query, Request

from app.dashboard.api.common import (
    DEFAULT_EVENT_LIMIT,
    MAX_EVENT_LIMIT,
    _last_live_event_id,
    _list_live_events,
    get_session_factory,
    TaskRepository,
)

router = APIRouter()


@router.get("/events")
async def api_get_events(
    task_id: int | None = None,
    mission_id: int | None = None,
    after_id: int | None = None,
    limit: int = Query(DEFAULT_EVENT_LIMIT, ge=1, le=MAX_EVENT_LIMIT),
):
    """Live feed событий для Office UI. api_request по умолчанию скрыт. mission_id — алиас task_id."""
    if mission_id is not None and task_id is not None and mission_id != task_id:
        raise HTTPException(status_code=400, detail="mission_id и task_id не совпадают")
    effective_id = mission_id if mission_id is not None else task_id
    Session = get_session_factory()
    with Session() as session:
        events = _list_live_events(session, task_id=effective_id, after_id=after_id, limit=limit)
        return {
            "events": events,
            "mission_id": effective_id,
            "last_event_id": events[-1]["id"] if events else (after_id or _last_live_event_id(session, task_id=effective_id)),
        }


@router.post("/audit")
async def api_audit_event(request: Request):
    """Записать audit event (MCP tool invoke). Body: {event_type, payload, task_id?, request_id?}."""
    body = await request.json() or {}
    event_type = body.get("event_type")
    payload = body.get("payload", {})
    task_id = body.get("task_id")
    request_id = body.get("request_id")
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type required")
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        if request_id:
            payload = {**payload, "request_id": request_id}
        repo.add_audit_event(event_type=event_type, task_id=task_id, payload=payload)
    return {"ok": True}
