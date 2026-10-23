"""Explicit scoped HTTP surface. No global-owner dependency or client actor IDs."""

from dataclasses import asdict
import hmac
import json
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.auth import get_owner_api_key
from app.shared.dashboard_session import request_has_owner_session
from app.storage.models import AuditEvent, Handoff, Project, Task
from app.storage.repositories import get_engine
from app.workspaces.access import Scope, ScopeDenied, ScopedRepository

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _denied(scope=None):
    # Dedicated short transaction: caller rollback must not erase a denial.
    payload = (
        {
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "principal_id": scope.principal_id,
        }
        if scope
        else {"scoped_auth_denied": True, "workspace_id": -1}
    )
    with Session(get_engine()) as audit:
        audit.add(
            AuditEvent(event_type="workspace_access_denied", payload_json=payload)
        )
        audit.commit()
    raise HTTPException(status_code=403, detail="Scoped access denied")


def _bindings():
    if os.getenv("WORKSPACE_ACCESS_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        bindings = json.loads(os.getenv("WORKSPACE_PRINCIPAL_BINDINGS_JSON", "[]"))
        if not isinstance(bindings, list):
            raise ValueError()
        tokens = []
        for binding in bindings:
            principal, env_name = binding["principal_id"], binding["key_env"]
            if (
                not isinstance(principal, str)
                or not principal.strip()
                or not isinstance(env_name, str)
                or not env_name.startswith("WORKSPACE_KEY_")
            ):
                raise ValueError()
            token = os.environ[env_name]
            if not token or token == get_owner_api_key():
                raise ValueError()
            tokens.append((principal, token))
        if len({token for _, token in tokens}) != len(tokens):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=503, detail="Scoped authentication unavailable"
        ) from None
    return tokens


def _principal(request):
    from app.workspaces.browser_session import COOKIE, resolve

    tokens = _bindings()
    provided = request.headers.get("x-api-key", "")
    owner = os.getenv("WORKSPACE_OWNER_PRINCIPAL_ID", "").strip()
    if (
        owner
        and provided
        and hmac.compare_digest(provided.encode(), get_owner_api_key().encode())
    ):
        return owner
    for principal, token in tokens:
        if provided and hmac.compare_digest(provided.encode(), token.encode()):
            return principal
    browser_principal = (
        resolve(request.cookies.get(COOKIE), tokens) if not provided else None
    )
    if browser_principal:
        if (
            request.method not in {"GET", "HEAD"}
            and request.headers.get("x-workspace-request") != "1"
        ):
            _denied()
        return browser_principal
    if not provided and owner and request_has_owner_session(request):
        if (
            request.method not in {"GET", "HEAD"}
            and request.headers.get("x-workspace-request") != "1"
        ):
            _denied()
        return owner
    _denied()


def scoped_repo(workspace_id: int, project_id: int, request: Request):
    scope = Scope(_principal(request), workspace_id, project_id)
    with Session(get_engine()) as session:
        repo = ScopedRepository(session, scope)
        try:
            repo._authorize("read")
            yield repo
        except ScopeDenied:
            session.rollback()
            _denied(scope)


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    owner_text: str = Field(min_length=1, max_length=20000)


@router.get("/{workspace_id}/projects/{project_id}/tasks")
def tasks(repo=Depends(scoped_repo)):
    return [asdict(task) for task in repo.tasks()]


@router.post("/{workspace_id}/projects/{project_id}/tasks", status_code=201)
def create_task(body: TaskInput, repo=Depends(scoped_repo)):
    task = repo.create_task(body.owner_text)
    repo.session.commit()
    return asdict(task)


@router.get("/{workspace_id}/projects/{project_id}/tasks/{task_id}")
def task(task_id: int, repo=Depends(scoped_repo)):
    return asdict(repo.task(task_id))


@router.get("/{workspace_id}/projects/{project_id}/memory")
def memory(repo=Depends(scoped_repo)):
    return [asdict(row) for row in repo.memories()]


@router.get(
    "/{workspace_id}/projects/{project_id}/tasks/{task_id}/artifacts/{artifact_id}"
)
def artifact(task_id: int, artifact_id: int, repo=Depends(scoped_repo)):
    repo.task(task_id)
    artifact = repo.session.scalar(
        select(Handoff).where(Handoff.id == artifact_id, Handoff.task_id == task_id)
    )
    if (
        not artifact
        or not artifact.md_path
        or (artifact.payload_json or {}).get("classification") != "internal"
        or (artifact.payload_json or {}).get("usage_rights") != "owner_authorized"
    ):
        _denied(repo.scope)
    from app.workspaces.files import read_scoped_file

    return Response(
        read_scoped_file(repo, task_id, artifact.md_path),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment",
            "X-Content-Type-Options": "nosniff",
        },
    )


class PatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str = Field(min_length=1, max_length=64)
    patch_text: str = Field(min_length=1, max_length=200000)


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_sha256: str = Field(pattern="^[0-9a-f]{64}$")


class PatchDecision(ProposalInput):
    decision: str = Field(pattern="^(approve|rework)$")


def _patch_call(fn, *args):
    from app.workspaces.patch_executor import ExecutionConflict

    try:
        return fn(*args)
    except ExecutionConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.get("/{workspace_id}/projects/{project_id}/execution/profiles")
def execution_profiles(repo=Depends(scoped_repo)):
    from app.workspaces import patch_executor as executor

    if os.getenv("WORKSPACE_PATCH_EXECUTION_ENABLED", "false") != "true":
        return {"enabled": False, "profiles": []}
    values = _patch_call(executor.profiles, repo.scope)
    return {
        "enabled": True,
        "profiles": [
            {"id": p["id"], "repository": p["repository"]} for p in values.values()
        ],
    }


@router.get("/{workspace_id}/projects/{project_id}/tasks/{task_id}/execution")
def execution_state(task_id: int, repo=Depends(scoped_repo)):
    from app.workspaces.patch_executor import snapshot

    return _patch_call(snapshot, repo, task_id)


@router.post("/{workspace_id}/projects/{project_id}/tasks/{task_id}/execution/prepare")
def execution_prepare(task_id: int, body: PatchInput, repo=Depends(scoped_repo)):
    from app.workspaces.patch_executor import prepare

    return _patch_call(prepare, repo, task_id, body.profile_id, body.patch_text)


@router.post("/{workspace_id}/projects/{project_id}/tasks/{task_id}/execution/decision")
def execution_decision(task_id: int, body: PatchDecision, repo=Depends(scoped_repo)):
    from app.workspaces.patch_executor import decide

    return _patch_call(decide, repo, task_id, body.proposal_sha256, body.decision)


@router.post(
    "/{workspace_id}/projects/{project_id}/tasks/{task_id}/execution/start",
    status_code=202,
)
def execution(
    task_id: int,
    body: ProposalInput | None = None,
    repo=Depends(scoped_repo),
):
    from app.workspaces.patch_executor import start

    repo.task(task_id)
    if body is None:
        raise HTTPException(status_code=409, detail="No prepared scoped patch")
    run_id = _patch_call(start, repo, task_id, body.proposal_sha256)
    return {"task_id": task_id, "run_id": run_id, "status": "EXECUTING"}


@router.get(
    "/{workspace_id}/projects/{project_id}/overview", response_class=HTMLResponse
)
def overview(repo=Depends(scoped_repo)):
    import html

    rows = repo.tasks()
    return HTMLResponse(
        "<!doctype html><html lang='ru'><meta charset='utf-8'><title>Рабочее пространство</title><h1>Задачи проекта</h1><ul>"
        + "".join(
            f"<li>#{row.id} · {html.escape(row.status)} · {html.escape(row.owner_text)}</li>"
            for row in rows
        )
        + "</ul></html>"
    )


def legacy_task_guard(request):
    """Protect in-memory runtime/stop routes too; SQL filtering alone is insufficient."""
    import re
    from sqlalchemy import or_
    from app.shared.auth import dashboard_web_key_ok
    from app.shared.dashboard_link import verify_task_link

    if request.url.path.startswith("/api/workspaces/"):
        return None
    match = re.search(r"/(?:tasks|missions)/(\d+)(?:/|$)", request.url.path)
    query_id = request.query_params.get("task_id", "")
    task_id = (
        int(match.group(1)) if match else int(query_id) if query_id.isdigit() else None
    )
    if task_id is None:
        return None
    if not dashboard_web_key_ok(
        request, request.headers.get("x-api-key")
    ) and not verify_task_link(task_id, request.query_params.get("link", "")):
        return None  # Existing route authentication handles unauthenticated requests.
    with Session(get_engine()) as session:
        scoped = session.scalar(
            select(Task.id)
            .outerjoin(Project, Task.project_id == Project.id)
            .where(
                Task.id == task_id,
                or_(Task.workspace_id.is_not(None), Project.workspace_id.is_not(None)),
            )
        )
    if scoped is not None:
        try:
            _denied()
        except HTTPException:
            return JSONResponse(status_code=404, content={"detail": "Task not found"})
    return None
