"""Runtime mission/office routes from live dashboard (reconcile bridge).

Live-only paths: /missions, /mission/*, /office, login/logout, execution-pack, approve/pause/resume/cancel.
Productization /owner/* stays in app.dashboard.app.
"""
from __future__ import annotations

import html
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import get_dashboard_config
from app.business_execution.execution_engine import (
    apply_action_feedback,
    ensure_action_instance_blob,
    growth_insight_snapshot,
    pack_learning_quality,
)
from app.business_execution.owner_checklist import owner_protocol_for_dashboard
from app.business_execution.revenue import create_deal, create_lead, ensure_revenue_fields, task_revenue_summary
from app.dashboard.documents import (
    build_task_documents,
    latest_verdict_handoff,
    list_regular_handoffs,
    read_task_document,
)
from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.auth import (
    assert_dashboard_task_write,
    dashboard_web_key_ok,
    get_owner_api_key,
    normalize_owner_key_input,
    require_owner_key,
)
from app.shared.dashboard_link import verify_task_link
from app.shared.dashboard_session import (
    COOKIE_NAME as OWNER_SESSION_COOKIE,
    owner_password_ok,
    session_ttl_seconds,
    sign_owner_session,
)
from app.shared.redaction import redact, scrub_secrets
from app.shared.system_health import collect_system_health
from app.dashboard.api_router import apply_owner_decision, apply_merge_confirmation
from app.dashboard.business_view import (
    access_query_with_view,
    business_goal_display,
    business_value_text,
    default_dashboard_view,
    enrich_artifacts_for_template,
    enrich_workflow_steps_for_template,
    execution_from_scenario_dict,
    execution_pack_dict,
    exploration_bundle_dict,
    exploration_mode_active,
    exploration_selected_option_id,
    exploration_waiting_for_scenario,
    friendly_current_phase,
    gm_decision_dict,
    mission_headline,
    mission_list_row,
    next_business_step_text,
    owner_workstream_label,
    parse_view_mode,
    project_impact_blurb,
    impact_display,
)
from app.storage.run_persistence import register_orchestration_run_persistence
from app.orchestrator.runtime import get_orchestration_runtime
from app.orchestrator.sync_run import run_sync_orchestration

register_orchestration_run_persistence()

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runtime-mission"])
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

def _markdown_execution_from_scenario(task_id: int, exr: dict) -> str:
    """Экспорт dry-run execution в Markdown для Cursor/шаринга."""
    lines: list[str] = [
        f"# Подготовка к Cursor — Mission #{task_id}",
        "",
        "> Это **dry-run** (exploration): до pipeline и суда. Не путать с **Execution Pack** после court.",
        "",
    ]
    sel = exr.get("selected_option") if isinstance(exr.get("selected_option"), dict) else {}
    if sel:
        lines.extend(
            [
                f"## Выбранный сценарий: {sel.get('title', '—')}",
                "",
            ]
        )
    ps = exr.get("project_structure")
    if isinstance(ps, list) and ps:
        lines.append("## Структура проекта (план)")
        for p in ps:
            lines.append(f"- `{p}`")
        lines.append("")
    at = exr.get("agent_tasks")
    if isinstance(at, list) and at:
        lines.append("## Задачи агентам")
        for row in at:
            if isinstance(row, dict):
                ag = row.get("agent", "—")
                tk = row.get("task", "")
                lines.append(f"- **{ag}**: {tk}")
        lines.append("")
    cp = exr.get("cursor_prompts")
    if isinstance(cp, list) and cp:
        lines.append("## Cursor-промпты (по порядку)")
        for i, row in enumerate(cp, 1):
            if isinstance(row, dict):
                agent = row.get("agent", "agent")
                body = str(row.get("prompt") or "").strip()
                lines.append(f"### {i}. {agent}")
                lines.append("")
                lines.append("```text")
                lines.append(body)
                lines.append("```")
                lines.append("")
    note = exr.get("system_note")
    if note:
        lines.extend(["## Системное примечание", "", str(note), ""])
    return "\n".join(lines).rstrip() + "\n"

def build_api_key_query(request: Request) -> str:
    api_key = normalize_owner_key_input(request.query_params.get("api_key"))
    return f"?api_key={api_key}" if api_key else ""

def build_dashboard_access_query(request: Request) -> str:
    """Сохранить способ доступа для ссылок внутри HTML: ?link=… или ?api_key=…"""
    link = normalize_owner_key_input(request.query_params.get("link"))
    if link:
        return f"?link={quote(link, safe='')}"
    return build_api_key_query(request)

def _dashboard_task_html_access_ok(request: Request, task_id: int, link_token: str | None) -> bool:
    if dashboard_web_key_ok(request, request.headers.get("x-api-key")):
        return True
    tok = normalize_owner_key_input(link_token) or normalize_owner_key_input(request.query_params.get("link"))
    if tok and verify_task_link(task_id, tok):
        return True
    return False

def _invalid_or_expired_link_html() -> HTMLResponse:
    return HTMLResponse(
        content=(
            "<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Ссылка недействительна</title></head>"
            "<body style='font-family:system-ui;max-width:36rem;margin:2rem auto;'>"
            "<h1>Ссылка устарела или повреждена</h1>"
            "<p>Параметр <code>link</code> неверный или истёк. Откройте задачу из <strong>нового сообщения</strong> "
            "в Telegram или используйте <code>?api_key=</code>.</p>"
            "<p>Срок токена: <code>DASHBOARD_LINK_TTL_SECONDS</code> в .env.</p>"
            "</body></html>"
        ),
        status_code=403,
    )

def _dashboard_task_page_denied(request: Request, task_id: int, link: str | None) -> HTMLResponse | None:
    """None если доступ есть; иначе HTML-ответ ошибки."""
    if _dashboard_task_html_access_ok(request, task_id, link):
        return None
    if normalize_owner_key_input(request.query_params.get("link")) or normalize_owner_key_input(link):
        return _invalid_or_expired_link_html()
    return _dashboard_key_hint_response(request)

def _dashboard_key_hint_response(request: Request) -> HTMLResponse:
    """Простой вход для одного владельца: форма → cookie на 30 дней."""
    base = str(request.base_url).rstrip("/")
    path = request.url.path or "/"
    tail = f"?{request.url.query}" if request.url.query else ""
    path_esc = html.escape(path)
    tail_esc = html.escape(tail)
    next_path = html.escape(path + (f"?{request.url.query}" if request.url.query else ""))
    hdr = normalize_owner_key_input(request.headers.get("x-api-key"))
    q = normalize_owner_key_input(request.query_params.get("api_key"))
    key_attempt = bool(hdr or q)
    err = ""
    if key_attempt:
        err = (
            "<p class='err'>Ключ в URL/заголовке не принят. Введите пароль владельца в форме ниже "
            "(тот же, что <code>OWNER_API_KEY</code>, либо короткий <code>DASHBOARD_PIN</code> если задан).</p>"
        )

    return HTMLResponse(
        f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Вход — MyWave</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 26rem; margin: 2.5rem auto; padding: 0 1rem; line-height: 1.5; }}
    code {{ background: #f0f0f0; padding: 0.15rem 0.35rem; border-radius: 4px; word-break: break-all; font-size: 0.9em; }}
    .box {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 10px; padding: 1.1rem; margin: 1rem 0; }}
    label {{ display:block; font-weight:600; margin-bottom:0.35rem; }}
    input[type=password] {{ width:100%; box-sizing:border-box; padding:0.65rem 0.75rem; font-size:1rem; border:1px solid #ced4da; border-radius:8px; }}
    button {{ margin-top:0.85rem; width:100%; padding:0.7rem 1rem; font-size:1rem; border:0; border-radius:8px; background:#0f766e; color:#fff; cursor:pointer; }}
    button:hover {{ background:#0d9488; }}
    .err {{ color:#b91c1c; }}
    .muted {{ color:#64748b; font-size:0.92rem; }}
  </style>
</head>
<body>
  <h1>MyWave</h1>
  <p class="muted">Вход только для владельца. Один раз — и браузер запомнит на 30 дней.</p>
  {err}
  <div class="box">
    <form method="post" action="/login">
      <input type="hidden" name="next" value="{next_path}"/>
      <label for="password">Пароль владельца</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required autofocus/>
      <button type="submit">Войти</button>
    </form>
  </div>
  <p class="muted">Вы открыли: <code>{path_esc}{tail_esc}</code></p>
  <p class="muted">Проверка сервера: <a href="{base}/health">/health</a></p>
</body>
</html>""",
        status_code=200,
    )

def _cookie_secure(request: Request) -> bool:
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").lower()
    return proto == "https"

@router.post("/login")
async def dashboard_login(request: Request):
    """Простой вход: пароль → HttpOnly cookie (без api_key в URL)."""
    form = await request.form()
    password = form.get("password")
    next_raw = str(form.get("next") or "/").strip() or "/"
    if not next_raw.startswith("/") or next_raw.startswith("//"):
        next_raw = "/"
    if not owner_password_ok(str(password) if password is not None else None):
        return HTMLResponse(
            content=(
                "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'/><title>Ошибка входа</title></head>"
                "<body style='font-family:system-ui;max-width:26rem;margin:2rem auto;padding:0 1rem'>"
                "<h1>Неверный пароль</h1>"
                "<p>Проверьте значение из <code>OWNER_API_KEY</code> "
                "(или <code>DASHBOARD_PIN</code>, если задали короткий пин).</p>"
                "<p><a href='/'>Попробовать снова</a></p>"
                "</body></html>"
            ),
            status_code=401,
        )
    token = sign_owner_session()
    if not token:
        raise HTTPException(status_code=500, detail="Cannot create session: OWNER_API_KEY missing")
    resp = RedirectResponse(url=next_raw, status_code=303)
    resp.set_cookie(
        key=OWNER_SESSION_COOKIE,
        value=token,
        max_age=session_ttl_seconds(),
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        path="/",
    )
    return resp

@router.post("/logout")
async def dashboard_logout(request: Request):
    next_raw = "/"
    try:
        form = await request.form()
        cand = str(form.get("next") or "/").strip() or "/"
        if cand.startswith("/") and not cand.startswith("//"):
            next_raw = cand
    except Exception:
        pass
    resp = RedirectResponse(url=next_raw, status_code=303)
    resp.delete_cookie(OWNER_SESSION_COOKIE, path="/")
    return resp

@router.get("/logout")
async def dashboard_logout_get():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(OWNER_SESSION_COOKIE, path="/")
    return resp

def _document_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".txt":
        return "text/plain"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/octet-stream"

def _runner_snapshot(task_id: int) -> dict:
    return get_orchestration_runtime().snapshot(task_id)

def _workflow_status(task, runner: dict) -> str:
    if runner.get("state") in {"running", "stopping"}:
        return "running"
    if runner.get("state") == "cancelled":
        return "paused"
    if task.status in {"WAIT_OWNER", "EXECUTION_READY"}:
        return "waiting_owner"
    if task.status in {"DONE", "ARCHIVED"}:
        return "done"
    if task.status in {"REWORK", "NEED_INFO"}:
        return "paused"
    return "created"

def _phase_index(task) -> int:
    mapping = {
        "NEW": 0,
        "TRIAGED": 1,
        "IN_PIPELINE": 2,
        "IN_ROUNDTABLE": 3,
        "IN_COURT": 4,
        "EXECUTION_READY": 1,
        "WAIT_OWNER": 5,
        "APPROVED_WAIT_MERGE": 6,
        "DONE": 6,
        "ARCHIVED": 6}
    if task.status == "WAIT_OWNER" and exploration_waiting_for_scenario(task):
        # Иначе UI помечает pipeline/court как done, хотя exploration рано вышел до pipeline.
        return 1
    return mapping.get(task.status, 0)

def _workflow_steps(task, runner: dict) -> list[dict]:
    idx = _phase_index(task)
    steps: list[dict] = []
    agent_names = {h.step_name for h in (task.handoffs or []) if h.step_name}
    for i, phase in enumerate(WORKFLOW_PHASES):
        status = "pending"
        if i < idx:
            status = "done"
        if task.status == "WAIT_OWNER" and phase == "approval":
            status = "waiting_owner"
        elif runner.get("state") in {"running", "stopping"} and runner.get("phase") == phase:
            status = "running"
        elif task.status in {"REWORK", "NEED_INFO"} and i >= idx:
            status = "skipped"
        step_agents = sorted(a for a in agent_names if a.upper().startswith(phase[:2].upper()))
        steps.append(
            {
                "step_id": f"{task.id}:{phase}",
                "name": phase,
                "status": status,
                "agent_roles": step_agents}
        )
    return steps

def _nav_access_query(request: Request, form_view: str | None = None) -> str:
    """Сохранить api_key/link и режим view=business|system для ссылок и редиректов."""
    base = build_dashboard_access_query(request)
    raw: str | None = None
    if form_view in ("business", "system"):
        raw = form_view
    else:
        qv = request.query_params.get("view")
        if qv and str(qv).strip().lower() in ("business", "system"):
            raw = str(qv).strip().lower()
    if raw:
        return access_query_with_view(base, parse_view_mode(str(raw)))
    if not request.query_params.get("view") and not form_view:
        return access_query_with_view(base, default_dashboard_view())
    return base

def _workflow_summary(task) -> dict:
    runner = _runner_snapshot(task.id)
    steps = _workflow_steps(task, runner)
    done_steps = len([s for s in steps if s["status"] == "done"])
    waiting = task.status == "WAIT_OWNER"
    if exploration_waiting_for_scenario(task):
        current_step = "exploration"
    else:
        current_step = runner.get("phase") or ("approval" if waiting else "idle")
    return {
        "workflow_id": f"wf-{task.id}",
        "task_id": task.id,
        "status": _workflow_status(task, runner),
        "current_step": current_step,
        "progress_done": done_steps,
        "progress_total": len(steps),
        "steps": steps,
        "runner": runner}

async def _read_task_id_from_request(request: Request) -> int:
    tid, _ = await _read_task_id_and_view_from_request(request)
    return tid

async def _read_task_id_and_view_from_request(request: Request) -> tuple[int, str | None]:
    payload: dict = {}
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        payload = await request.json()
        view = None
    else:
        form = await request.form()
        payload = dict(form)
        raw_view = payload.get("view")
        view = str(raw_view).strip().lower() if raw_view else None
        if view not in ("business", "system"):
            view = None
    raw = payload.get("task_id")
    if raw is None:
        raise HTTPException(status_code=400, detail="task_id required")
    try:
        tid = int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="task_id must be int") from exc
    return tid, view

async def _optional_form_view(request: Request) -> str | None:
    try:
        form = await request.form()
        v = form.get("view")
        if v in ("business", "system"):
            return str(v).strip().lower()
    except Exception:
        pass
    return None

def _start_background_resume(task_id: int, *, source: str = "console_resume") -> dict:
    runtime = get_orchestration_runtime()

    def _target(control):
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            return run_sync_orchestration(repo, task_id, source=source, control=control) or {}

    return runtime.start(task_id, source=source, target=_target)

@router.get("/office", response_class=HTMLResponse)
async def office_index(request: Request, x_api_key: str | None = Header(None, alias="X-API-Key")):
    if not get_owner_api_key():
        raise HTTPException(status_code=500, detail="Server misconfiguration: OWNER_API_KEY not set")
    if not dashboard_web_key_ok(request, x_api_key):
        return _dashboard_key_hint_response(request)
    return templates.TemplateResponse(
        request,
        "office.html",
        {
            "api_key_query": build_api_key_query(request),
            "initial_task_id": None},
    )

@router.get("/office/tasks/{task_id}", response_class=HTMLResponse)
async def office_task_scene(
    request: Request,
    task_id: int,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    if not get_owner_api_key():
        raise HTTPException(status_code=500, detail="Server misconfiguration: OWNER_API_KEY not set")
    if not dashboard_web_key_ok(request, x_api_key):
        return _dashboard_key_hint_response(request)
    return templates.TemplateResponse(
        request,
        "office.html",
        {
            "api_key_query": build_api_key_query(request),
            "initial_task_id": task_id},
    )

@router.get("/tasks/{task_id}/artifacts/{artifact_id}", response_class=HTMLResponse)
async def artifact_detail(
    request: Request,
    task_id: int,
    artifact_id: int,
    link: str | None = Query(None),
):
    denied = _dashboard_task_page_denied(request, task_id, link)
    if denied is not None:
        return denied
    access_query = build_dashboard_access_query(request)
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
        return templates.TemplateResponse(
            request,
            "artifact_detail.html",
            {
                "task_id": task_id,
                "title": f"Artifact #{artifact_id}",
                "subtitle": handoff.step_name,
                "path": handoff.md_path,
                "content": redact(path.read_text(encoding="utf-8")),
                "api_key_query": access_query,
                "office_url": f"/office/tasks/{task_id}{access_query}"},
        )

@router.get("/tasks/{task_id}/report", response_class=HTMLResponse)
async def report_detail(request: Request, task_id: int, link: str | None = Query(None)):
    return await task_document_detail(request, task_id, "report", link=link)

@router.get("/tasks/{task_id}/documents/{document_key}", response_class=HTMLResponse)
async def task_document_detail(
    request: Request,
    task_id: int,
    document_key: str,
    link: str | None = Query(None),
):
    denied = _dashboard_task_page_denied(request, task_id, link)
    if denied is not None:
        return denied
    access_query = build_dashboard_access_query(request)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        document = read_task_document(task, document_key)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return templates.TemplateResponse(
            request,
            "artifact_detail.html",
            {
                "task_id": task_id,
                "title": document["title"],
                "subtitle": document["subtitle"],
                "path": document["path"],
                "content": document["content"],
                "api_key_query": access_query,
                "office_url": f"/office/tasks/{task_id}{access_query}"},
        )

@router.get("/tasks/{task_id}/documents/{document_key}/download")
async def task_document_download(
    request: Request,
    task_id: int,
    document_key: str,
    link: str | None = Query(None),
):
    denied = _dashboard_task_page_denied(request, task_id, link)
    if denied is not None:
        return denied
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        document = read_task_document(task, document_key)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        path = Path(document["path"])
        if not path.exists():
            raise HTTPException(status_code=404, detail="Document file not found")
        return FileResponse(path, filename=path.name, media_type=_document_media_type(path))

@router.post("/tasks/{task_id}/approve")
async def approve_task(request: Request, task_id: int):
    assert_dashboard_task_write(request, task_id)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        apply_owner_decision(repo, task_id, "approve", source="dashboard")
    return RedirectResponse(url=f"/tasks/{task_id}{build_dashboard_access_query(request)}", status_code=303)

@router.post("/tasks/{task_id}/rework")
async def rework_task(request: Request, task_id: int):
    assert_dashboard_task_write(request, task_id)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        apply_owner_decision(repo, task_id, "rework", source="dashboard")
    return RedirectResponse(url=f"/tasks/{task_id}{build_dashboard_access_query(request)}", status_code=303)

@router.post("/tasks/{task_id}/clarify")
async def clarify_task(request: Request, task_id: int):
    assert_dashboard_task_write(request, task_id)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        apply_owner_decision(repo, task_id, "clarify", source="dashboard")
    return RedirectResponse(url=f"/tasks/{task_id}{build_dashboard_access_query(request)}", status_code=303)

@router.post("/tasks/{task_id}/merged")
async def mark_merged_task(request: Request, task_id: int):
    assert_dashboard_task_write(request, task_id)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        apply_merge_confirmation(repo, task_id, source="dashboard")
    return RedirectResponse(url=f"/tasks/{task_id}{build_dashboard_access_query(request)}", status_code=303)

@router.get("/missions", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def missions_console(request: Request):
    """Owner Operating Console: обзор активных миссий и требуемых решений."""
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
        missions = []
        approvals = []
        for t in tasks:
            wf = _workflow_summary(t)
            proj = repo.get_project(t.project_id) if t.project_id else None
            row = mission_list_row(t, proj, wf)
            item = {
                **row,
                "summary": (t.summary or "")[:220]}
            missions.append(item)
            if item["needs_approval"]:
                approvals.append(item)
        exploration_pending = [m for m in missions if m.get("exploration_waiting")]
        health = collect_system_health()
        paused = [m for m in missions if m["workflow_status"] in {"paused", "failed"}]
        running = [m for m in missions if m["workflow_status"] == "running"]
    view_mode = (
        parse_view_mode(request.query_params.get("view"))
        if request.query_params.get("view")
        else default_dashboard_view()
    )
    access_query = _nav_access_query(request)
    base_auth = build_dashboard_access_query(request)
    return templates.TemplateResponse(
        request,
        "missions.html",
        {
            "api_key_query": access_query,
            "access_query_business": access_query_with_view(base_auth, "business"),
            "access_query_system": access_query_with_view(base_auth, "system"),
            "view_mode": view_mode,
            "missions": missions,
            "approvals": approvals,
            "exploration_pending": exploration_pending,
            "running_count": len(running),
            "paused_count": len(paused),
            "health": health},
    )

@router.get("/mission/{task_id}", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def mission_console_detail(request: Request, task_id: int):
    """Owner Operating Console: карточка миссии с workflow, approvals и артефактами."""
    view_mode = (
        parse_view_mode(request.query_params.get("view"))
        if request.query_params.get("view")
        else default_dashboard_view()
    )
    access_query = _nav_access_query(request)
    base_auth = build_dashboard_access_query(request)
    access_query_business = access_query_with_view(base_auth, "business")
    access_query_system = access_query_with_view(base_auth, "system")
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        project = repo.get_project(task.project_id) if task.project_id else None
        workflow = _workflow_summary(task)
        ws = owner_workstream_label(task, project)
        gm = gm_decision_dict(task)
        execution_pack = execution_pack_dict(task)
        all_tasks = repo.get_all_tasks()
        pack_learning = pack_learning_quality(str(execution_pack.get("pack_type") or "generic_pack"), all_tasks) if execution_pack else {}
        revenue_summary = task_revenue_summary(task.business_action_json or {})
        growth_insight = growth_insight_snapshot(all_tasks)
        owner_protocol = owner_protocol_for_dashboard(all_tasks, growth_insight)
        exploration_waiting = exploration_waiting_for_scenario(task)
        ex_from_scenario = execution_from_scenario_dict(task)
        exploration_bundle = exploration_bundle_dict(task)
        exploration_options = exploration_bundle.get("options") if isinstance(exploration_bundle.get("options"), list) else []
        emode = exploration_mode_active(task)
        esel = exploration_selected_option_id(task)
        logger.info(
            "EXPLORATION_UI_RENDER task_id=%s exploration_mode=%s selected_option_id=%s exploration_waiting=%s",
            task_id,
            emode,
            esel or None,
            exploration_waiting,
        )
        artifacts_raw = [
            {
                "id": h.id,
                "step_name": h.step_name,
                "path": h.md_path,
                "url": f"/tasks/{task_id}/artifacts/{h.id}{access_query}"}
            for h in list_regular_handoffs(task)
        ]
        artifacts = enrich_artifacts_for_template(artifacts_raw, ws)
        workflow_steps = enrich_workflow_steps_for_template(workflow.get("steps") or [], view_mode)
        workflow_display = {
            **workflow,
            "steps": workflow_steps,
            "current_step_display": friendly_current_phase(task, workflow, view_mode)}
        approvals = [
            {
                "decision": d.decision,
                "owner_approval": d.owner_approval,
                "at": d.created_at.isoformat() if d.created_at else None,
                "rationale": redact(d.rationale or "")}
            for d in (task.decisions or [])
        ]
        recent_events = [
            {
                "event_type": e.event_type,
                "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in sorted(
                task.audit_events or [],
                key=lambda e: e.created_at.isoformat() if e.created_at else "",
                reverse=True,
            )[:10]
        ]
    return templates.TemplateResponse(
        request,
        "mission_detail.html",
        {
            "api_key_query": access_query,
            "access_query_business": access_query_business,
            "access_query_system": access_query_system,
            "view_mode": view_mode,
            "task": task,
            "workflow": workflow_display,
            "artifacts": artifacts,
            "approvals": approvals,
            "recent_events": recent_events,
            "needs_approval": task.status == "WAIT_OWNER" and not exploration_waiting,
            "exploration_waiting": exploration_waiting,
            "exploration_options": exploration_options,
            "exploration_bundle": exploration_bundle,
            "exploration_selected_option_id": esel or None,
            "execution_from_scenario": ex_from_scenario,
            "has_execution_from_scenario": bool(ex_from_scenario),
            "business_type": task.business_type or "-",
            "impact_level": task.impact_level or "-",
            "impact_score": task.impact_score,
            "impact_display": impact_display(task),
            "business_action": task.business_action_json or {},
            "project": project,
            "owner_workstream": ws,
            "mission_title": mission_headline(task),
            "business_goal_display": business_goal_display(task, project),
            "business_value_text": business_value_text(task),
            "next_business_step": next_business_step_text(task),
            "impact_on_project": project_impact_blurb(task, project, gm),
            "gm_decision": gm,
            "execution_pack": execution_pack,
            "pack_learning": pack_learning,
            "revenue_summary": revenue_summary,
            "growth_insight": growth_insight,
            "owner_protocol": owner_protocol},
    )

@router.get("/mission/{task_id}/execution-pack", response_class=HTMLResponse, dependencies=[Depends(require_owner_key)])
async def mission_execution_pack_view(request: Request, task_id: int):
    access_query = _nav_access_query(request)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        project = repo.get_project(task.project_id) if task.project_id else None
        all_tasks = repo.get_all_tasks()
        tracked = ensure_action_instance_blob(task, project, all_tasks=all_tasks)
        if not tracked:
            raise HTTPException(status_code=404, detail="Execution pack not found")
        repo.update_task(task_id, business_action_json=tracked)
        pack = tracked.get("execution_pack") or {}
        action = tracked.get("action_instance") or {}
        metrics = tracked.get("execution_metrics") or {}
        scoring = tracked.get("execution_scoring") or {}
        learning = tracked.get("pack_learning") or {}
        revenue = task_revenue_summary(tracked)
        task_view = {"id": task.id}
        project_name = project.name if project else ""
    return templates.TemplateResponse(
        request,
        "execution_pack.html",
        {
            "api_key_query": access_query,
            "task": task_view,
            "project_name": project_name,
            "pack": pack,
            "action": action,
            "metrics": metrics,
            "scoring": scoring,
            "learning": learning,
            "revenue": revenue},
    )

@router.post("/mission/{task_id}/execution-pack/action", dependencies=[Depends(require_owner_key)])
async def mission_execution_pack_action(request: Request, task_id: int):
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)

    status = str(payload.get("status") or "").strip().lower()
    if status not in {"pending", "in_progress", "done", "skipped"}:
        raise HTTPException(status_code=400, detail="status must be pending|in_progress|done|skipped")

    owner_feedback = str(payload.get("owner_feedback") or "")
    result_summary = str(payload.get("result_summary") or "")
    result_type = str(payload.get("result_type") or "")
    result_value = str(payload.get("result_value") or "")
    notes = str(payload.get("notes") or "")

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        project = repo.get_project(task.project_id) if task.project_id else None
        all_tasks = repo.get_all_tasks()
        tracked = ensure_action_instance_blob(task, project, all_tasks=all_tasks)
        if not tracked:
            raise HTTPException(status_code=404, detail="Execution pack not found")
        updated = apply_action_feedback(
            tracked,
            status=status,
            owner_feedback=owner_feedback,
            result_summary=result_summary,
            result_type=result_type,
            result_value=result_value,
            notes=notes,
        )
        updated = ensure_revenue_fields(updated)
        action = updated.get("action_instance") if isinstance(updated.get("action_instance"), dict) else {}
        pack = updated.get("execution_pack") if isinstance(updated.get("execution_pack"), dict) else {}
        source_action_id = str(action.get("action_id") or "")
        if not source_action_id:
            source_action_id = f"act-{task_id}-manual"
            action["action_id"] = source_action_id
            updated["action_instance"] = action
        source_pack_type = str(pack.get("pack_type") or action.get("action_type") or "generic_pack")

        money_result = str(payload.get("money_result") or "").strip().lower()
        lead_channel = str(payload.get("lead_channel") or "")
        lead_notes = str(payload.get("lead_notes") or notes)
        lead_value = str(payload.get("lead_value_estimate") or result_value)
        sale_amount = str(payload.get("sale_amount") or result_value)
        sale_notes = str(payload.get("sale_notes") or notes)
        if money_result == "lead" or result_type == "lead":
            updated = create_lead(
                updated,
                project_id=task.project_id,
                action_id=source_action_id,
                pack_type=source_pack_type,
                channel=lead_channel or "manual",
                notes=lead_notes or result_summary,
                value_estimate=lead_value,
            )
        elif money_result == "sale" or result_type == "sale":
            updated = create_deal(
                updated,
                project_id=task.project_id,
                action_id=source_action_id,
                pack_type=source_pack_type,
                amount=sale_amount,
                notes=sale_notes or result_summary,
            )
        elif money_result == "contact" or result_type == "partner":
            updated = create_lead(
                updated,
                project_id=task.project_id,
                action_id=source_action_id,
                pack_type=source_pack_type,
                channel=lead_channel or "contact",
                notes=lead_notes or result_summary,
                value_estimate=lead_value,
                status="contacted",
            )

        repo.update_task(task_id, business_action_json=updated)
        refreshed = repo.get_task(task_id)
        if refreshed:
            enriched = ensure_action_instance_blob(refreshed, project, all_tasks=repo.get_all_tasks())
            if enriched:
                repo.update_task(task_id, business_action_json=enriched)
        repo.add_audit_event(
            "execution_action_feedback",
            task_id=task_id,
            payload={
                "status": status,
                "result_type": result_type,
                "result_value": result_value[:200]},
        )

    if "application/json" in ctype:
        return {"ok": True, "task_id": task_id, "status": status, "revenue": task_revenue_summary(updated)}
    return RedirectResponse(url=f"/mission/{task_id}/execution-pack{_nav_access_query(request)}", status_code=303)

@router.get("/mission/{task_id}/execution-pack.md", dependencies=[Depends(require_owner_key)])
async def mission_execution_pack_markdown(request: Request, task_id: int):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        project = repo.get_project(task.project_id) if task.project_id else None
        all_tasks = repo.get_all_tasks()
        tracked = ensure_action_instance_blob(task, project, all_tasks=all_tasks)
        if not tracked:
            raise HTTPException(status_code=404, detail="Execution pack not found")
        pack = tracked.get("execution_pack") or {}
        action = tracked.get("action_instance") or {}

    md = [
        f"# Execution Pack · Mission #{task_id}",
        "",
        "## Действие",
        str(pack.get("action_title") or "-"),
        "",
        "## Зачем",
        str(pack.get("why") or "-"),
        "",
        "## Готовые шаги",
    ]
    for step in pack.get("ready_steps", []) or ["-"]:
        md.append(f"- {step}")
    md.extend(
        [
            "",
            "## Как выполнить",
            str(pack.get("how_to_execute") or "-"),
            "",
            "## Ожидаемый результат",
            str(pack.get("expected_result") or "-"),
            "",
            "## Action Instance",
            f"- action_id: {action.get('action_id', '-')}",
            f"- status: {action.get('status', '-')}",
            f"- started_at: {action.get('started_at', '-')}",
            f"- completed_at: {action.get('completed_at', '-')}",
            f"- result_summary: {action.get('result_summary', '-')}",
            f"- owner_feedback: {action.get('owner_feedback', '-')}",
            "",
        ]
    )
    content = "\n".join(md)
    return HTMLResponse(content=content, media_type="text/markdown")

@router.get("/workflow/{task_id}", dependencies=[Depends(require_owner_key)])
async def workflow_console_view(task_id: int):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return _workflow_summary(task)

@router.get("/artifacts/{task_id}", dependencies=[Depends(require_owner_key)])
async def artifacts_console_view(task_id: int):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {
            "task_id": task_id,
            "artifacts": [
                {
                    "id": h.id,
                    "step_name": h.step_name,
                    "path": h.md_path}
                for h in list_regular_handoffs(task)
            ]}

@router.post("/approve", dependencies=[Depends(require_owner_key)])
async def console_approve(request: Request):
    task_id, form_view = await _read_task_id_and_view_from_request(request)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        result = apply_owner_decision(repo, task_id, "approve", source="console")
    if "application/json" in (request.headers.get("content-type") or "").lower():
        return result
    return RedirectResponse(url=f"/mission/{task_id}{_nav_access_query(request, form_view)}", status_code=303)

@router.post("/pause", dependencies=[Depends(require_owner_key)])
async def console_pause(request: Request):
    task_id, form_view = await _read_task_id_and_view_from_request(request)
    runtime = get_orchestration_runtime()
    try:
        runner = runtime.request_stop(task_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        repo.add_audit_event("workflow_paused_by_owner", task_id=task_id, payload={"source": "console"})
    if "application/json" in (request.headers.get("content-type") or "").lower():
        return {"ok": True, "task_id": task_id, "runner": runner}
    return RedirectResponse(url=f"/mission/{task_id}{_nav_access_query(request, form_view)}", status_code=303)

@router.post("/resume", dependencies=[Depends(require_owner_key)])
async def console_resume(request: Request):
    task_id, form_view = await _read_task_id_and_view_from_request(request)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status in {"NEW", "NEED_INFO", "REWORK"}:
            repo.update_task(task_id, status="REWORK")
        try:
            runner = _start_background_resume(task_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        repo.add_audit_event("workflow_resumed_by_owner", task_id=task_id, payload={"source": "console"})
    if "application/json" in (request.headers.get("content-type") or "").lower():
        return {"ok": True, "task_id": task_id, "runner": runner}
    return RedirectResponse(url=f"/mission/{task_id}{build_dashboard_access_query(request)}", status_code=303)

@router.post("/cancel", dependencies=[Depends(require_owner_key)])
async def console_cancel(request: Request):
    task_id = await _read_task_id_from_request(request)
    runtime = get_orchestration_runtime()
    snapshot = runtime.snapshot(task_id)
    if snapshot.get("is_active"):
        try:
            runtime.request_stop(task_id)
        except RuntimeError:
            pass
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        repo.update_task(task_id, status="ARCHIVED")
        repo.add_audit_event("workflow_cancelled_by_owner", task_id=task_id, payload={"source": "console"})
    if "application/json" in (request.headers.get("content-type") or "").lower():
        return JSONResponse({"ok": True, "task_id": task_id, "status": "ARCHIVED"})
    return RedirectResponse(url=f"/missions{_nav_access_query(request, form_view)}", status_code=303)

