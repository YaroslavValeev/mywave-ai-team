"""Project discovery and browser shell; grants remain authoritative on every request."""

from datetime import datetime
from pathlib import Path
import hmac

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.storage.models import (
    Project,
    ProjectAccessGrant,
    Workspace,
    WorkspaceMembership,
)
from app.storage.repositories import get_engine
from app.workspaces import browser_session
from app.workspaces.web import _bindings, _denied, _principal

router = APIRouter(prefix="/api/workspaces", tags=["project-console"])
ASSETS = Path(__file__).with_name("console_assets")


@router.get("/projects")
def projects(request: Request):
    principal = _principal(request)
    now = datetime.utcnow()
    roles = {"reader", "writer", "owner"}
    with Session(get_engine()) as session:
        rows = session.execute(
            select(
                Workspace, Project, WorkspaceMembership.role, ProjectAccessGrant.role
            )
            .join(Project, Project.workspace_id == Workspace.id)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .join(ProjectAccessGrant, ProjectAccessGrant.project_id == Project.id)
            .where(
                WorkspaceMembership.principal_id == principal,
                ProjectAccessGrant.principal_id == principal,
                WorkspaceMembership.role.in_(roles),
                ProjectAccessGrant.role.in_(roles),
                WorkspaceMembership.revoked_at.is_(None),
                ProjectAccessGrant.revoked_at.is_(None),
                or_(
                    WorkspaceMembership.expires_at.is_(None),
                    WorkspaceMembership.expires_at > now,
                ),
                or_(
                    ProjectAccessGrant.expires_at.is_(None),
                    ProjectAccessGrant.expires_at > now,
                ),
            )
            .order_by(Workspace.id, Project.id)
        )
        return [
            {
                "workspace_id": workspace.id,
                "workspace_name": workspace.name,
                "project_id": project.id,
                "project_name": project.name,
                "can_create": membership in {"writer", "owner"}
                and grant in {"writer", "owner"},
            }
            for workspace, project, membership, grant in rows
        ]


def _secure_transport(request):
    # Plain HTTP is permitted only on the loopback QA/development host.
    if request.url.scheme != "https" and request.url.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise HTTPException(status_code=400, detail="HTTPS required")


@router.post("/session")
def login(request: Request):
    tokens = _bindings()
    _secure_transport(request)
    supplied = request.headers.get("x-api-key", "")
    for principal, key in tokens:
        if supplied and hmac.compare_digest(supplied.encode(), key.encode()):
            response = JSONResponse(
                {"authenticated": True, "expires_in": browser_session.TTL}
            )
            response.set_cookie(
                browser_session.COOKIE,
                browser_session.issue(principal, key),
                max_age=browser_session.TTL,
                path=browser_session.PATH,
                secure=request.url.scheme == "https",
                httponly=True,
                samesite="strict",
            )
            return response
    _denied()


@router.delete("/session")
def logout(request: Request):
    _bindings()
    if request.headers.get("x-workspace-request") != "1":
        _denied()
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(browser_session.COOKIE, path=browser_session.PATH)
    return response


def asset(filename, media_type):
    _bindings()  # Disabled scope exposes neither login nor static console routes.
    return Response(
        (ASSETS / filename).read_bytes(),
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/console")
def page():
    return asset("index.html", "text/html")


@router.get("/console.js")
def javascript():
    return asset("console.js", "text/javascript")


@router.get("/console.css")
def stylesheet():
    return asset("console.css", "text/css")
