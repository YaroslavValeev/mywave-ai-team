# app/dashboard/app.py — FastAPI + Jinja (HF-1: auth, v0.2 Control API)
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_dashboard_config
from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.auth import require_owner_key
from app.shared.redaction import redact, scrub_secrets
from app.dashboard.api_router import router as api_router

app = FastAPI(title="MyWave AI-TEAM Dashboard", version="0.2.0")
app.include_router(api_router)

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


@app.middleware("http")
async def audit_api_middleware(request: Request, call_next):
    """Audit для /api/* запросов."""
    start = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        latency_ms = int((time.perf_counter() - start) * 1000)
        task_id = None
        parts = path.strip("/").split("/")
        if "tasks" in parts:
            try:
                idx = parts.index("tasks")
                if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                    task_id = int(parts[idx + 1])
            except (ValueError, IndexError):
                pass
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            payload = {"actor": "owner", "route": path, "task_id": task_id, "status_code": response.status_code, "latency_ms": latency_ms}
            req_id = request.headers.get("X-Request-Id")
            if req_id:
                payload["request_id"] = req_id
            repo.add_audit_event(event_type="api_request", task_id=task_id, payload=payload)
    return response


def run_dashboard():
    import uvicorn
    from app.shared.auth import require_owner_key_at_startup
    require_owner_key_at_startup()
    cfg = get_dashboard_config()
    host = cfg.get("host", "0.0.0.0")
    port = int(cfg.get("port", os.getenv("DASHBOARD_PORT", "8080")))
    uvicorn.run(app, host=host, port=port)
