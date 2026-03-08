# app/dashboard/api_router.py — Control API (v0.2)
# Endpoints: tasks CRUD, artifacts, pipeline/run, logs.
# Auth: X-API-Key. Audit: в app.py middleware.

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from app.orchestrator.triage import run_triage
from app.orchestrator.pipeline import run_pipeline
from app.orchestrator.roundtable import run_roundtable
from app.orchestrator.court import run_court
from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.auth import require_owner_key
from app.shared.redaction import redact, scrub_secrets

router = APIRouter(prefix="/api", tags=["api"], dependencies=[Depends(require_owner_key)])


@router.get("/tasks")
async def api_list_tasks():
    """Список задач."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
        return [
            {
                "id": t.id,
                "domain": t.domain,
                "status": t.status,
                "criticality": t.criticality,
                "pr_url": t.pr_url,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ]


@router.post("/tasks")
async def api_create_task(request: Request):
    """Создать задачу. Body: {owner_text} или {domain, task_type, payload, criticality}."""
    body = await request.json() or {}
    owner_text = body.get("owner_text")
    if not owner_text:
        domain = body.get("domain", "PRODUCT_DEV")
        task_type = body.get("task_type", "general")
        payload = body.get("payload", {})
        owner_text = f"#TASK Domain: {domain}, Type: {task_type}. Payload: {payload}"
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text=owner_text)
        if body.get("domain"):
            triage_result = run_triage(owner_text)
            repo.update_task(
                task.id,
                domain=triage_result.get("domain"),
                task_type=triage_result.get("task_type"),
                criticality=triage_result.get("criticality"),
                plan_or_execute=triage_result.get("plan_or_execute"),
            )
        return {"id": task.id, "status": task.status, "domain": task.domain}


@router.get("/tasks/{task_id}")
async def api_get_task(task_id: int, raw: int = 0, _=Depends(require_owner_key)):
    """Детали задачи."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        owner_text_raw = task.owner_text or ""
        allow_pii = "ALLOW_PII" in owner_text_raw
        if raw == 1 and allow_pii:
            owner_text_display = scrub_secrets(owner_text_raw)
        else:
            owner_text_display = redact(owner_text_raw)
        return {
            "id": task.id,
            "owner_text": owner_text_display,
            "status": task.status,
            "domain": task.domain,
            "task_type": task.task_type,
            "criticality": task.criticality,
            "report_path": task.report_path,
            "summary": redact(task.summary or ""),
            "pr_url": task.pr_url,
            "commit_sha": task.commit_sha,
            "ci_url": task.ci_url,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "decisions": [{"decision": d.decision, "owner_approval": d.owner_approval} for d in task.decisions],
            "handoffs": [{"id": h.id, "step_name": h.step_name, "md_path": h.md_path} for h in sorted(task.handoffs, key=lambda x: x.step_index)],
        }


@router.patch("/tasks/{task_id}")
async def api_update_task(task_id: int, request: Request):
    """Обновить задачу. Body: {status, pr_url, commit_sha, ci_url, summary, ...}."""
    body = await request.json() or {}
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        allowed = {"status", "pr_url", "commit_sha", "ci_url", "summary", "report_path"}
        updates = {k: v for k, v in body.items() if k in allowed}
        if not updates:
            return {"id": task_id, "status": task.status}
        task = repo.update_task(task_id, **updates)
        if "pr_url" in updates and updates.get("pr_url"):
            import os
            from app.bot.notify import notify_pr_ready
            dash_url = os.getenv("DASHBOARD_URL", "https://agm.mywavetreaning.ru")
            asyncio.create_task(notify_pr_ready(task_id, updates["pr_url"], task.summary or "", dash_url))
        return {"id": task.id, "status": task.status}


@router.get("/tasks/{task_id}/artifacts")
async def api_list_artifacts(task_id: int):
    """Список артефактов (handoffs) по задаче."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        artifacts = [
            {"id": h.id, "step_index": h.step_index, "step_name": h.step_name, "md_path": h.md_path}
            for h in sorted(task.handoffs, key=lambda x: x.step_index)
        ]
        return {"artifacts": artifacts}


@router.get("/artifacts/{artifact_id}")
async def api_get_artifact(artifact_id: int, task_id: int):
    """Содержимое артефакта (handoff md)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        handoff = next((h for h in task.handoffs if h.id == artifact_id), None)
        if not handoff or not handoff.md_path:
            raise HTTPException(status_code=404, detail="Artifact not found")
        path = Path(handoff.md_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Artifact file not found")
        content = path.read_text(encoding="utf-8")
        return {"content": redact(content)}


@router.post("/tasks/{task_id}/pipeline/run")
async def api_run_pipeline(task_id: int):
    """Запустить pipeline (triage → pipeline → roundtable → court)."""
    from app.shared.audit import log_audit
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        triage_result = run_triage(task.owner_text)
        repo.update_task(task_id, status="IN_PIPELINE", **{k: v for k, v in triage_result.items() if v})
        log_audit(repo, "pipeline_start", task_id=task_id, payload={"source": "api"})
        pipeline_result = run_pipeline(task_id, triage_result, repo)
        repo.update_task(task_id, status="IN_ROUNDTABLE")
        roundtable_result = run_roundtable(task_id, triage_result, pipeline_result, repo)
        repo.update_task(task_id, status="IN_COURT")
        court_result = run_court(task_id, triage_result, pipeline_result, roundtable_result, repo)
        report_path = court_result.get("report_path")
        summary = court_result.get("summary", "")[:1200]
        repo.update_task(task_id, status="WAIT_OWNER", report_path=report_path, summary=summary)
        log_audit(repo, "pipeline_done", task_id=task_id, payload={"report_path": report_path})
        return {"ok": True, "status": "WAIT_OWNER", "report_path": report_path}


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


@router.get("/tasks/{task_id}/logs")
async def api_get_logs(task_id: int):
    """Логи по задаче (audit_events без секретов)."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        from app.storage.models import AuditEvent
        events = session.query(AuditEvent).filter(AuditEvent.task_id == task_id).order_by(AuditEvent.created_at).all()
        logs = [
            {"event_type": e.event_type, "payload": e.payload_json, "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in events
        ]
        return {"logs": logs}
