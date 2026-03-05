# app/dashboard/app.py — FastAPI + Jinja (HF-1: auth)
import os
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_dashboard_config
from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.auth import require_owner_key
from app.shared.redaction import redact, scrub_secrets

app = FastAPI(title="MyWave AI-TEAM Dashboard", version="0.1.0")

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/health")
async def health():
    """Без auth — для healthcheck."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/tasks", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def list_tasks(request: Request):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
        items = [
            {
                "id": t.id,
                "domain": t.domain or "-",
                "status": t.status,
                "criticality": t.criticality or "-",
                "created_at": t.created_at.isoformat() if t.created_at else "-",
            }
            for t in tasks
        ]
    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": items})


@app.get("/tasks/{task_id}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def task_detail(request: Request, task_id: int, raw: int = 0):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # HF-2: redaction. raw=1 + ALLOW_PII в тексте → PII можно, но scrub_secrets всегда
        owner_text_raw = task.owner_text or ""
        allow_pii = "ALLOW_PII" in owner_text_raw
        if raw == 1 and allow_pii:
            owner_text_display = scrub_secrets(owner_text_raw)
        else:
            owner_text_display = redact(owner_text_raw)

        summary_display = redact(task.summary or "")

        timeline = []
        if task.created_at:
            timeline.append({"status": "NEW", "at": task.created_at, "note": "Created"})
        if task.updated_at and task.status != "NEW":
            timeline.append({"status": task.status, "at": task.updated_at, "note": f"Status: {task.status}"})

        decisions = [{"decision": d.decision, "rationale": redact(d.rationale or ""), "owner_approval": d.owner_approval, "at": d.created_at} for d in task.decisions]
        handoffs = [{"step": h.step_name, "md_path": h.md_path} for h in sorted(task.handoffs, key=lambda x: x.step_index)]

        return templates.TemplateResponse(
            "task_detail.html",
            {
                "request": request,
                "task": task,
                "owner_text_display": owner_text_display,
                "summary_display": summary_display,
                "timeline": timeline,
                "decisions": decisions,
                "handoffs": handoffs,
            },
        )


@app.get("/api/tasks", dependencies=[Depends(require_owner_key)])
async def api_list_tasks():
    """JSON API для задач."""
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
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ]


@app.get("/api/tasks/{task_id}", dependencies=[Depends(require_owner_key)])
async def api_task_detail(task_id: int, raw: int = 0):
    """JSON API для деталей задачи."""
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
            "owner_text": owner_text_display[:200] + "..." if len(owner_text_display) > 200 else owner_text_display,
            "status": task.status,
            "domain": task.domain,
            "task_type": task.task_type,
            "criticality": task.criticality,
            "report_path": task.report_path,
            "summary": redact(task.summary or ""),
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "decisions": [{"decision": d.decision, "owner_approval": d.owner_approval} for d in task.decisions],
        }


def run_dashboard():
    import uvicorn
    from app.shared.auth import require_owner_key_at_startup
    require_owner_key_at_startup()
    cfg = get_dashboard_config()
    host = cfg.get("host", "0.0.0.0")
    port = int(cfg.get("port", os.getenv("DASHBOARD_PORT", "8080")))
    uvicorn.run(app, host=host, port=port)
