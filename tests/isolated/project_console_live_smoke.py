import http.cookiejar
from datetime import datetime
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.storage.models import (
    Base,
    Workspace,
    Project,
    WorkspaceMembership,
    ProjectAccessGrant,
)
from app.storage.repositories import get_engine

assert os.environ["DATABASE_URL"].split("/")[-1].startswith("ai_team_workspace_qa_")
engine = get_engine()
Base.metadata.create_all(engine)
with Session(engine) as session:
    workspace = Workspace(
        slug="smoke", name="QA workspace", kind="MYWAVE", owner_id="qa-owner"
    )
    session.add(workspace)
    session.flush()
    project = Project(workspace_id=workspace.id, slug="qa-project", name="QA project")
    other = Project(workspace_id=workspace.id, slug="private", name="Private")
    session.add_all([project, other])
    session.flush()
    grant = ProjectAccessGrant(
        project_id=project.id, principal_id="qa-owner", role="writer"
    )
    session.add_all(
        [
            WorkspaceMembership(
                workspace_id=workspace.id, principal_id="qa-owner", role="owner"
            ),
            grant,
        ]
    )
    session.commit()
    wid, pid, other_id, grant_id = workspace.id, project.id, other.id, grant.id

jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
base = "http://127.0.0.1:8080/api/workspaces"


def call(path, method="GET", body=None, headers=None):
    req = urllib.request.Request(
        base + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with client.open(req, timeout=10) as response:
            content = response.read()
            return response.status, (
                json.loads(content)
                if "application/json" in response.headers.get("Content-Type", "")
                else content
            )
    except urllib.error.HTTPError as error:
        return error.code, None


process = subprocess.Popen(
    [
        "python",
        "-m",
        "uvicorn",
        "app.dashboard.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
        "--no-access-log",
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
try:
    ready = False
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError("QA app exited")
        try:
            if call("/console")[0] == 200:
                ready = True
                break
        except OSError:
            pass
        time.sleep(1)
    assert ready
    assert call("/projects")[0] == 403
    assert (
        call("/session", "POST", headers={"X-API-Key": os.environ["OWNER_API_KEY"]})[0]
        == 403
    )
    assert (
        call("/session", "POST", headers={"X-API-Key": os.environ["WORKSPACE_KEY_QA"]})[
            0
        ]
        == 200
    )
    visible = call("/projects")[1]
    assert len(visible) == 1 and visible[0]["project_id"] == pid
    route = f"/{wid}/projects/{pid}/tasks"
    assert call(route) == (200, [])
    assert call(route, "POST", {"owner_text": "no csrf"})[0] == 403
    code, created = call(
        route, "POST", {"owner_text": "Docker live smoke"}, {"X-Workspace-Request": "1"}
    )
    assert code == 201 and created["status"] == "NEW" and created["project_id"] == pid
    assert len(call(route)[1]) == 1
    assert call(f"/{wid}/projects/{other_id}/tasks")[0] == 403
    with Session(engine) as session:
        session.get(ProjectAccessGrant, grant_id).revoked_at = datetime.utcnow()
        session.commit()
    assert call("/projects") == (200, [])
    assert call(route)[0] == 403
    assert call("/session", "DELETE", headers={"X-Workspace-Request": "1"})[0] == 200
    assert call("/projects")[0] == 403
    print(
        json.dumps(
            {
                "real_uvicorn_http": "passed",
                "task_created_NEW": True,
                "cross_scope_denied": True,
                "live_revocation": "passed",
                "cookie_logout": "passed",
            }
        )
    )
finally:
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
