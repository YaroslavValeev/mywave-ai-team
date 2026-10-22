"""Browser and HTTP isolation on real disposable databases; no external services."""

from datetime import datetime, timedelta
import json

import pytest
from sqlalchemy import select

from test_workspace_schema import engine, session  # noqa: F401
from test_workspace_integration import configured, SCOPED, OWNER, prefix  # noqa: F401
from app.storage.models import ProjectAccessGrant, Task, WorkspaceMembership
from app.workspaces import browser_session


@pytest.fixture
def browser(configured):
    from fastapi.testclient import TestClient
    from app.dashboard.app import app

    with TestClient(app, base_url="https://testserver") as client:
        yield client


def login(browser):
    response = browser.post("/api/workspaces/session", headers=SCOPED)
    assert response.status_code == 200
    return response


def test_browser_login_cookie_and_discovery(browser, configured):
    response = login(browser)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert "Path=/api/workspaces" in cookie and "Max-Age=900" in cookie
    assert SCOPED["X-API-Key"] not in cookie
    assert response.headers["cache-control"] == "private, no-store"
    projects = browser.get("/api/workspaces/projects")
    assert projects.json() == [
        {
            "workspace_id": configured[1],
            "workspace_name": "Scope",
            "project_id": configured[2],
            "project_name": "media",
            "can_create": True,
        }
    ]
    assert browser.get(prefix(configured) + "/tasks").status_code == 200
    assert (
        browser.get(
            "/api/workspaces/projects", headers={"X-API-Key": "wrong"}
        ).status_code
        == 403
    )


def test_cookie_create_requires_marker_and_server_owned_scope(
    browser, configured, session
):
    login(browser)
    path = prefix(configured) + "/tasks"
    assert browser.post(path, json={"owner_text": "blocked"}).status_code == 403
    headers = {"X-Workspace-Request": "1"}
    assert (
        browser.post(
            path,
            headers=headers,
            json={"owner_text": "forged", "principal_id": "other"},
        ).status_code
        == 422
    )
    response = browser.post(
        path, headers=headers, json={"owner_text": "<script>new task</script>"}
    )
    assert response.status_code == 201
    task = session.get(Task, response.json()["id"])
    assert task.workspace_id == configured[1] and task.project_id == configured[2]
    assert task.status == "NEW"
    assert (
        browser.post(
            prefix(configured) + f"/tasks/{task.id}/execution/start",
            headers=headers,
            json={},
        ).status_code
        == 409
    )
    assert browser.get(f"/api/tasks/{task.id}", headers=OWNER).status_code == 404


@pytest.mark.parametrize("target", ["membership", "grant"])
@pytest.mark.parametrize("condition", ["revoked", "expired", "reader"])
def test_live_permission_changes(browser, configured, session, target, condition):
    login(browser)
    if target == "membership":
        record = session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.principal_id == "alice"
            )
        )
    else:
        record = session.get(ProjectAccessGrant, configured[5])
    if condition == "reader":
        record.role = "reader"
    elif condition == "revoked":
        record.revoked_at = datetime.utcnow()
    else:
        record.expires_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()
    projects = browser.get("/api/workspaces/projects").json()
    if condition == "reader":
        assert len(projects) == 1 and projects[0]["can_create"] is False
        assert browser.get(prefix(configured) + "/tasks").status_code == 200
    else:
        assert projects == []
        assert browser.get(prefix(configured) + "/tasks").status_code == 403
    assert (
        browser.post(
            prefix(configured) + "/tasks",
            headers={"X-Workspace-Request": "1"},
            json={"owner_text": "denied"},
        ).status_code
        == 403
    )


def test_dedicated_session_isolated_from_shared_cookie_and_other_scope(
    browser, configured
):
    assert browser.post("/api/workspaces/session", headers=OWNER).status_code == 403
    from app.shared.dashboard_session import COOKIE_NAME, sign_owner_session

    browser.cookies.set(COOKIE_NAME, sign_owner_session())
    assert browser.get("/api/workspaces/projects").status_code == 403
    login(browser)
    assert (
        browser.get(
            f"/api/workspaces/{configured[1]}/projects/{configured[2]+1}/tasks"
        ).status_code
        == 403
    )
    assert browser.delete("/api/workspaces/session").status_code == 403
    assert (
        browser.delete(
            "/api/workspaces/session", headers={"X-Workspace-Request": "1"}
        ).status_code
        == 200
    )
    assert browser.get("/api/workspaces/projects").status_code == 403


def test_rotation_and_expiry_invalidate_cookie(browser, configured, monkeypatch):
    login(browser)
    value = browser.cookies.get(browser_session.COOKIE)
    assert browser_session.resolve(value, [("alice", SCOPED["X-API-Key"])]) == "alice"
    assert browser_session.resolve(value, [("alice", "rotated")]) is None
    assert (
        browser_session.resolve(value + "modified", [("alice", SCOPED["X-API-Key"])])
        is None
    )
    monkeypatch.setenv("WORKSPACE_KEY_ALICE", "rotated")
    assert browser.get("/api/workspaces/projects").status_code == 403
    monkeypatch.setattr(browser_session.time, "time", lambda: 10000)
    value = browser_session.issue("alice", "key")
    monkeypatch.setattr(browser_session.time, "time", lambda: 10900)
    assert browser_session.resolve(value, [("alice", "key")]) is None


def test_shell_disabled_https_policy_and_no_inline_credentials(
    browser, configured, monkeypatch
):
    response = browser.get("/api/workspaces/console?api_key=ignored")
    assert response.status_code == 200
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "ignored" not in response.text and SCOPED["X-API-Key"] not in response.text
    script = browser.get("/api/workspaces/console.js")
    assert (
        script.status_code == 200
        and "localStorage" not in script.text
        and "innerHTML" not in script.text
    )
    assert browser.get("/api/workspaces/console.css").status_code == 200
    assert (
        browser.post(
            "http://example.test/api/workspaces/session", headers=SCOPED
        ).status_code
        == 400
    )
    monkeypatch.setenv("WORKSPACE_ACCESS_ENABLED", "false")
    for path in ("console", "console.js", "console.css", "projects"):
        assert browser.get("/api/workspaces/" + path).status_code == 404
    assert browser.post("/api/workspaces/session", headers=SCOPED).status_code == 404


@pytest.mark.parametrize(
    "value", ["", "x.y", "not-a-cookie", "[]", "x" * 1025, "bnVsbA.00", "W10.00"]
)
def test_malformed_cookies_fail_closed(value):
    assert browser_session.resolve(value, [("alice", "key")]) is None
