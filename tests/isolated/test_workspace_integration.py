"""Real HTTP, legacy SQL, artifact and execution boundaries in disposable databases."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, sessionmaker

from test_workspace_schema import engine, session  # noqa: F401
from test_scoped_access import seed
from app.storage.models import (
    AuditEvent,
    Handoff,
    MemoryEntry,
    Project,
    ProjectAccessGrant,
    Task,
)
from app.workspaces.access import ScopeDenied
from app.workspaces.legacy import LegacySession


@pytest.fixture
def configured(session, engine, monkeypatch, tmp_path):
    import app.storage.repositories as storage

    monkeypatch.setattr(storage, "_engine", engine)
    monkeypatch.setattr(
        storage,
        "_session_factory",
        sessionmaker(engine, class_=LegacySession, autoflush=False),
    )
    monkeypatch.setenv("OWNER_API_KEY", "synthetic_owner_key_for_tests")
    monkeypatch.setenv("WORKSPACE_ACCESS_ENABLED", "true")
    monkeypatch.delenv("WORKSPACE_OWNER_PRINCIPAL_ID", raising=False)
    monkeypatch.setenv(
        "WORKSPACE_PRINCIPAL_BINDINGS_JSON",
        json.dumps([{"principal_id": "alice", "key_env": "WORKSPACE_KEY_ALICE"}]),
    )
    monkeypatch.setenv("WORKSPACE_KEY_ALICE", "synthetic_scoped_key_for_tests")
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("ORCHESTRATION_ENGINE", "rule_based")
    monkeypatch.setenv("TELEGRAM_PROACTIVE_NOTIFY_ENABLED", "false")
    repo, workspace, projects, _, grant = seed(session)
    task = session.scalar(select(Task).where(Task.project_id == projects[0].id))
    legacy_project = Project(slug="legacy-http", name="legacy")
    session.add(legacy_project)
    session.flush()
    legacy = Task(project_id=legacy_project.id, owner_text="public legacy")
    session.add(legacy)
    session.commit()
    return repo, workspace.id, projects[0].id, task.id, legacy.id, grant.id, tmp_path


def client():
    from fastapi.testclient import TestClient
    from app.dashboard.app import app

    return TestClient(app, raise_server_exceptions=True)


def prefix(data):
    return f"/api/workspaces/{data[1]}/projects/{data[2]}"


SCOPED = {"X-API-Key": "synthetic_scoped_key_for_tests"}
OWNER = {"X-API-Key": "synthetic_owner_key_for_tests"}


def test_legacy_sql_hides_scoped_rows_and_linked_events(configured, session, engine):
    _, wid, pid, tid, lid, _, _ = configured
    session.add_all(
        [
            Handoff(
                task_id=tid,
                step_index=1,
                step_name="private",
                payload_json={"secret": "private"},
            ),
            AuditEvent(task_id=tid, event_type="private"),
            AuditEvent(
                event_type="private-global",
                payload_json={"workspace_id": wid, "project_id": pid},
            ),
            AuditEvent(task_id=lid, event_type="legacy"),
        ]
    )
    session.commit()
    with LegacySession(engine) as legacy:
        assert [row.id for row in legacy.scalars(select(Task))] == [lid]
        assert legacy.get(Task, tid) is None
        assert not list(legacy.scalars(select(Handoff)))
        assert [row.event_type for row in legacy.scalars(select(AuditEvent))] == [
            "legacy"
        ]
        assert not list(legacy.scalars(select(MemoryEntry)))
        assert legacy.get(Project, pid) is None
        legacy.execute(
            update(Task).where(Task.id == tid).values(owner_text="unauthorized")
        )
        legacy.commit()
    session.expire_all()
    assert session.get(Task, tid).owner_text == "media"


def test_legacy_write_and_bulk_bypasses_block(configured, engine):
    _, wid, pid, tid, lid, _, _ = configured
    with LegacySession(engine) as legacy:
        legacy.add(Task(project_id=pid, owner_text="wrong context"))
        with pytest.raises(ScopeDenied):
            legacy.commit()
        legacy.rollback()
        with pytest.raises(ScopeDenied):
            legacy.execute(text("SELECT * FROM tasks"))
        with pytest.raises(ScopeDenied):
            legacy.bulk_update_mappings(Task, [{"id": tid, "owner_text": "wrong"}])
        with pytest.raises(ScopeDenied):
            legacy.execute(update(Task).where(Task.id == lid).values(workspace_id=wid))


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "/runtime",
        "/thread",
        "/scene",
        "/documents",
        "/logs",
        "/artifacts",
        "/outcome-metrics",
    ],
)
def test_old_api_cannot_bypass_scope_or_read_runtime(configured, suffix):
    response = client().get(f"/api/tasks/{configured[3]}{suffix}", headers=OWNER)
    assert response.status_code == 404
    assert "media" not in response.text


@pytest.mark.parametrize(
    "suffix",
    [
        "/pipeline/start",
        "/pipeline/stop",
        "/execution/start",
        "/approve",
        "/merged",
        "/rework",
    ],
)
def test_old_writes_do_not_launch_or_change_scoped_mission(configured, session, suffix):
    assert (
        client().post(f"/api/tasks/{configured[3]}{suffix}", headers=OWNER).status_code
        == 404
    )
    session.expire_all()
    assert session.get(Task, configured[3]).status == "NEW"


def test_scoped_authentication_create_read_and_revoke(configured, session):
    c = client()
    url = prefix(configured)
    assert c.get(url + "/tasks", headers=OWNER).status_code == 403
    assert (
        c.get(
            url + "/tasks", headers={**SCOPED, "X-Principal-ID": "fake-owner"}
        ).json()[0]["owner_text"]
        == "media"
    )
    result = c.post(
        url + "/tasks", headers=SCOPED, json={"owner_text": "created in scope"}
    )
    assert (
        c.post(url + "/tasks", headers=SCOPED, json={"owner_text": "   "}).status_code
        == 422
    )
    assert result.status_code == 201, result.text
    assert result.json()["workspace_id"] == configured[1]
    assert (
        c.post(
            url + "/tasks",
            headers=SCOPED,
            json={"owner_text": "x", "principal_id": "owner", "workspace_id": 999},
        ).status_code
        == 422
    )
    assert "no-store" in c.get(url + "/tasks", headers=SCOPED).headers["Cache-Control"]
    row = session.get(ProjectAccessGrant, configured[5])
    from datetime import datetime

    row.revoked_at = datetime.utcnow()
    session.commit()
    assert c.get(url + "/tasks", headers=SCOPED).status_code == 403
    session.expire_all()
    assert (
        session.scalar(
            select(AuditEvent.id).where(
                AuditEvent.event_type == "workspace_access_denied"
            )
        )
        is not None
    )


def test_feature_off_and_signed_legacy_links_do_not_grant_scope(
    configured, monkeypatch
):
    from app.shared.dashboard_link import sign_task_link

    c = client()
    assert (
        c.get(
            f"/tasks/{configured[3]}?link=" + sign_task_link(configured[3])
        ).status_code
        == 404
    )
    assert c.get(prefix(configured) + "/tasks?principal_id=alice").status_code == 403
    monkeypatch.setenv("WORKSPACE_ACCESS_ENABLED", "false")
    assert c.get(prefix(configured) + "/tasks", headers=SCOPED).status_code == 404


def test_cookie_identity_requires_explicit_binding_and_csrf_header(
    configured, monkeypatch
):
    from app.shared.dashboard_session import COOKIE_NAME, sign_owner_session

    monkeypatch.setenv("WORKSPACE_OWNER_PRINCIPAL_ID", "alice")
    c = client()
    c.cookies.set(COOKIE_NAME, sign_owner_session())
    url = prefix(configured) + "/tasks"
    assert c.get(url).status_code == 200
    assert c.post(url, json={"owner_text": "csrf rejected"}).status_code == 403
    assert (
        c.post(
            url,
            headers={"X-Workspace-Request": "1"},
            json={"owner_text": "same-origin approved"},
        ).status_code
        == 201
    )
    assert c.get(url, headers={"X-API-Key": "wrong-explicit-key"}).status_code == 403


def test_legacy_scope_fields_are_not_silently_discarded(configured):
    c = client()
    assert (
        c.post(
            "/api/tasks",
            headers=OWNER,
            json={
                "owner_text": "must not become legacy",
                "workspace_id": configured[1],
            },
        ).status_code
        == 400
    )
    assert (
        c.patch(
            f"/api/tasks/{configured[4]}",
            headers=OWNER,
            json={"workspace_id": configured[1]},
        ).status_code
        == 400
    )


def test_inconsistent_memory_link_is_not_retrieved(configured, session):
    repo, wid, pid, _, _, _, _ = configured
    foreign_task = session.scalar(
        select(Task).where(Task.project_id != pid, Task.workspace_id == wid)
    )
    session.add(
        MemoryEntry(
            workspace_id=wid,
            project_id=pid,
            task_id=foreign_task.id,
            scope="note",
            content="incorrectly linked",
        )
    )
    session.commit()
    assert [row.content for row in repo.memories()] == ["media"]


def test_scoped_artifacts_need_owned_path_rights_and_fresh_grant(configured, session):
    _, wid, pid, tid, lid, _, root = configured
    file = (
        root
        / "workspaces"
        / str(wid)
        / "projects"
        / str(pid)
        / "tasks"
        / f"task_{tid}"
        / "report.txt"
    )
    file.parent.mkdir(parents=True)
    file.write_text("scoped artifact", encoding="utf-8")
    handoff = Handoff(
        task_id=tid,
        step_index=1,
        step_name="doc",
        md_path=str(file),
        payload_json={"classification": "internal", "usage_rights": "owner_authorized"},
    )
    session.add(handoff)
    session.commit()
    url = prefix(configured) + f"/tasks/{tid}/artifacts/{handoff.id}"
    assert client().get(url, headers=SCOPED).content == b"scoped artifact"
    handoff.md_path = str(root / "outside.txt")
    (root / "outside.txt").write_text("must not leak")
    session.commit()
    assert client().get(url, headers=SCOPED).status_code == 403
    handoff.md_path = str(file)
    handoff.payload_json = {
        "classification": "sensitive",
        "usage_rights": "owner_authorized",
    }
    session.commit()
    assert client().get(url, headers=SCOPED).status_code == 403


def test_legacy_file_pointer_and_hardlink_do_not_expose_scoped_files(
    configured, session
):
    from app.workspaces.files import legacy_path

    _, wid, pid, tid, lid, _, root = configured
    private = root / "old-flat.txt"
    private.write_text("private classified file")
    session.add(
        Handoff(
            task_id=tid,
            step_index=1,
            step_name="private",
            md_path=str(private),
            payload_json={},
        )
    )
    session.commit()
    with pytest.raises(ScopeDenied):
        legacy_path(private)
    alias = root / "alias.txt"
    alias.hardlink_to(private)
    with pytest.raises(ScopeDenied):
        legacy_path(alias)


def test_business_cache_drops_reclassified_rows(configured, session, engine):
    from app.dashboard.api.common import _BUSINESS_CACHE, _get_cached_business_payload
    from app.storage.repositories import TaskRepository

    _, wid, pid, tid, lid, _, _ = configured
    with LegacySession(engine) as legacy:
        _BUSINESS_CACHE["updated_at_ts"] = 0
        first = _get_cached_business_payload(TaskRepository(legacy))[0]
        assert first["project_metrics"]["active_tasks"] == 1
    task = session.get(Task, lid)
    task.workspace_id = wid
    task.project_id = pid
    session.commit()
    with LegacySession(engine) as legacy:
        second = _get_cached_business_payload(TaskRepository(legacy))[0]
        assert second["project_metrics"]["active_tasks"] == 0


def test_scoped_execution_fails_closed_without_profile(configured, session):
    from app.execution.service import _validated_request, ExecutionRequestError
    from app.orchestrator.sync_run import run_sync_orchestration
    from app.storage.repositories import TaskRepository

    assert (
        client()
        .post(
            prefix(configured) + f"/tasks/{configured[3]}/execution/start",
            headers=SCOPED,
        )
        .status_code
        == 409
    )
    with pytest.raises(ExecutionRequestError, match="scoped executor"):
        _validated_request(session.get(Task, configured[3]))
    with pytest.raises(ScopeDenied):
        run_sync_orchestration(TaskRepository(session), configured[3])
