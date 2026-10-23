"""Real disposable SQL/Git; publication is stubbed to prevent live GitHub writes."""

from datetime import datetime
import json
from pathlib import Path
import subprocess

import pytest
from sqlalchemy import select

from test_workspace_schema import engine, session  # noqa: F401
from test_workspace_integration import (
    configured,
    client,
    prefix,
    SCOPED,
    OWNER,
)  # noqa: F401
from app.storage.models import (
    Decision,
    Handoff,
    Run,
    Task,
    WorkspaceMembership,
    ProjectAccessGrant,
)
from app.workspaces import patch_executor as executor


def client():
    from fastapi.testclient import TestClient
    from app.dashboard.app import app

    return TestClient(app, base_url="https://testserver")


PATCH = "diff --git a/readme.md b/readme.md\n--- a/readme.md\n+++ b/readme.md\n@@ -1 +1,2 @@\n base\n+approved change\n"


@pytest.fixture
def setup(configured, session, monkeypatch, tmp_path):
    root = tmp_path / "clones" / "project"
    root.mkdir(parents=True)

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(root), *args], stderr=subprocess.PIPE
        )

    git("init")
    git("config", "core.autocrlf", "false")
    git("config", "user.name", "Scoped QA")
    git("config", "user.email", "qa@example.invalid")
    git("remote", "add", "origin", "https://github.com/example/scoped.git")
    (root / "readme.md").write_text("base\n", newline="\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_small.py").write_text(
        "def test_ok():\n    assert 2 + 2 == 4\n", newline="\n"
    )
    git("add", ".")
    git("commit", "-m", "Initial test source")
    value = {
        "id": "club-box",
        "workspace_id": configured[1],
        "project_id": configured[2],
        "workspace_path": str(root),
        "repository": "example/scoped",
        "validation_image": "sha256:" + "1" * 64,
        "token_env": "WORKSPACE_EXECUTION_TOKEN_CLUB",
    }
    monkeypatch.setenv("WORKSPACE_PATCH_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("WORKSPACE_PATCH_WORKER_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", str(session.bind.url))
    monkeypatch.setenv(executor.PROFILE_ENV, json.dumps([value]))
    monkeypatch.setenv("WORKSPACE_PATCH_ROOTS_JSON", json.dumps([str(root.parent)]))
    monkeypatch.setenv(
        "WORKSPACE_EXECUTION_TOKEN_CLUB", "synthetic-project-execution-credential"
    )
    monkeypatch.setenv("EXECUTION_ALLOWED_ROOTS_JSON", "[]")
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    return configured, root, value


def api_path(data):
    return prefix(data) + f"/tasks/{data[3]}/execution"


def prepare(http, data):
    response = http.post(
        api_path(data) + "/prepare",
        headers=SCOPED,
        json={"profile_id": "club-box", "patch_text": PATCH},
    )
    assert response.status_code == 200, response.text
    return response.json()["proposal_sha256"]


def elevate(data, session):
    membership = session.scalar(
        select(WorkspaceMembership).where(WorkspaceMembership.principal_id == "alice")
    )
    membership.role = "owner"
    session.get(ProjectAccessGrant, data[5]).role = "owner"
    session.commit()


def approve(http, data, sha):
    return http.post(
        api_path(data) + "/decision",
        headers=SCOPED,
        json={"proposal_sha256": sha, "decision": "approve"},
    )


def test_real_prepare_read_approve_and_rework(setup, session):
    data, root, _ = setup
    with client() as http:
        sha = prepare(http, data)
        state = http.get(api_path(data), headers=SCOPED).json()
        assert state["status"] == "WAIT_OWNER"
        assert state["proposal"]["patch_text"] == PATCH
        assert state["proposal"]["plan"]["merge_allowed"] is False
        assert (root / "readme.md").read_text() == "base\n"
        assert approve(http, data, sha).status_code == 403  # Writer is not owner.
        elevate(data, session)
        assert approve(http, data, "f" * 64).status_code == 409
        response = http.post(
            api_path(data) + "/decision",
            headers=SCOPED,
            json={"proposal_sha256": sha, "decision": "rework"},
        )
        assert response.json()["status"] == "REWORK"
        assert approve(http, data, sha).status_code == 409
        next_sha = prepare(http, data)
        assert next_sha != sha
        assert approve(http, data, next_sha).json()["status"] == "EXECUTION_READY"
    session.expire_all()
    assert session.get(Task, data[3]).rework_cycles == 1
    assert len(list(session.scalars(select(Decision)))) == 2


@pytest.mark.parametrize("change", ["profile", "credential", "task", "scope"])
def test_approval_binds_all_mutable_inputs(setup, session, monkeypatch, change):
    data, _, value = setup
    with client() as http:
        sha = prepare(http, data)
        elevate(data, session)
        if change == "profile":
            value["validation_image"] = "sha256:" + "2" * 64
            monkeypatch.setenv(executor.PROFILE_ENV, json.dumps([value]))
        elif change == "credential":
            monkeypatch.setenv(
                value["token_env"], "rotated-project-execution-credential"
            )
        elif change == "task":
            session.get(Task, data[3]).owner_text = "New scope requires fresh approval"
            session.commit()
        else:
            value["project_id"] += 1
            monkeypatch.setenv(executor.PROFILE_ENV, json.dumps([value]))
        assert approve(http, data, sha).status_code == 409


def test_feature_flag_authentication_cross_scope_and_cookie_csrf(setup, monkeypatch):
    data, _, _ = setup
    with client() as http:
        assert http.get(prefix(data) + "/execution/profiles", headers=SCOPED).json()[
            "enabled"
        ]
        for headers in ({}, OWNER, {"X-API-Key": "wrong"}):
            assert http.get(api_path(data), headers=headers).status_code == 403
        bad = prefix(data).replace(f"projects/{data[2]}", f"projects/{data[2]+1}")
        assert (
            http.post(
                bad + f"/tasks/{data[3]}/execution/prepare",
                headers=SCOPED,
                json={"profile_id": "club-box", "patch_text": PATCH},
            ).status_code
            == 403
        )
        assert http.post("/api/workspaces/session", headers=SCOPED).status_code == 200
        assert (
            http.post(
                api_path(data) + "/prepare",
                json={"profile_id": "club-box", "patch_text": PATCH},
            ).status_code
            == 403
        )
        monkeypatch.setenv("WORKSPACE_PATCH_EXECUTION_ENABLED", "false")
        assert http.get(
            prefix(data) + "/execution/profiles", headers=SCOPED
        ).json() == {"enabled": False, "profiles": []}
        assert (
            http.post(
                api_path(data) + "/prepare",
                headers=SCOPED,
                json={"profile_id": "club-box", "patch_text": PATCH},
            ).status_code
            == 409
        )


@pytest.mark.parametrize(
    "failure", ["dirty", "shared_token", "root", "overlap", "secret"]
)
def test_unsafe_profile_checkout_or_patch_is_rejected(setup, monkeypatch, failure):
    data, root, value = setup
    patch = PATCH
    if failure == "dirty":
        (root / "keep-me.txt").write_text("owner changes")
    elif failure == "shared_token":
        monkeypatch.setenv(value["token_env"], SCOPED["X-API-Key"])
    elif failure == "root":
        monkeypatch.setenv("WORKSPACE_PATCH_ROOTS_JSON", "[]")
    elif failure == "overlap":
        monkeypatch.setenv("EXECUTION_ALLOWED_ROOTS_JSON", json.dumps([str(root)]))
    else:
        patch += "+token=" + "x" * 25
    with client() as http:
        response = http.post(
            api_path(data) + "/prepare",
            headers=SCOPED,
            json={"profile_id": "club-box", "patch_text": patch},
        )
        assert response.status_code == 409
    assert (root / "readme.md").read_text() == "base\n"


def ready(setup, session):
    data, root, value = setup
    with client() as http:
        sha = prepare(http, data)
        elevate(data, session)
        assert approve(http, data, sha).status_code == 200
    return data, root, value, sha


def test_actual_git_worker_reaches_pr_without_legacy_access_or_merge(
    setup, session, monkeypatch
):
    data, root, value, sha = ready(setup, session)
    calls = []
    original_command = executor.command

    def command(args, **kwargs):
        calls.append(args)
        if args[0] == "gh":
            assert kwargs["env"]["GH_TOKEN"] == "synthetic-project-execution-credential"
            assert "OWNER_API_KEY" not in kwargs["env"]
            if args[1] == "api":
                return b"true\n"
            return b"https://github.com/example/scoped/pull/123\n"
        if "push" in args:
            return b""
        return original_command(args, **kwargs)

    monkeypatch.setattr(executor, "command", command)
    validated = []
    monkeypatch.setattr(
        executor, "sandbox", lambda root, value, patch: validated.append(patch)
    )
    with client() as http:
        response = http.post(
            api_path(data) + "/start", headers=SCOPED, json={"proposal_sha256": sha}
        )
        assert response.status_code == 202
        from app.workspaces.patch_worker import run_once

        assert run_once()["processed"] is True
        assert run_once()["processed"] is False
        state = http.get(api_path(data), headers=SCOPED).json()
        assert state["status"] == "APPROVED_WAIT_MERGE", state
        assert state["run"]["state"] == "completed" and not state["run"]["is_active"]
        assert state["pr_url"].endswith("/pull/123") and len(state["commit_sha"]) == 40
        assert (
            http.post(
                api_path(data) + "/start", headers=SCOPED, json={"proposal_sha256": sha}
            ).status_code
            == 409
        )
        assert http.get(f"/api/tasks/{data[3]}", headers=OWNER).status_code == 404
    assert validated == [PATCH.encode()]
    assert (root / "readme.md").read_text() == "base\napproved change\n"
    assert not (root / ".git" / "mywave-scoped-execution.lock").exists()
    assert not any("merge" in command or "deploy" in command for command in calls)


@pytest.mark.parametrize(
    "failure", ["tests", "revoked", "base", "publish", "owner_downgraded", "rotated"]
)
def test_worker_failures_preserve_changes_and_release_claim(
    setup, session, monkeypatch, failure
):
    data, root, value, sha = ready(setup, session)

    def sandbox(*_):
        if failure == "tests":
            raise executor.ExecutionConflict("Validation failed")

    monkeypatch.setattr(executor, "sandbox", sandbox)
    original = executor.command

    def command(args, **kwargs):
        if args[:2] == ["gh", "api"]:
            return b"true\n"
        if "push" in args:
            if "--dry-run" in args:
                return b""
            raise executor.ExecutionConflict("Publication unavailable")
        return original(args, **kwargs)

    monkeypatch.setattr(executor, "command", command)
    # Queue separately to model permission/base changes before a worker starts.
    repo = data[0]
    run_id = executor.start(repo, data[3], sha)
    if failure == "revoked":
        session.get(ProjectAccessGrant, data[5]).revoked_at = datetime.utcnow()
        session.commit()
    if failure == "base":
        subprocess.run(
            ["git", "-C", str(root), "commit", "--allow-empty", "-m", "Changed base"],
            check=True,
            capture_output=True,
        )
    if failure == "owner_downgraded":
        session.get(ProjectAccessGrant, data[5]).role = "writer"
        session.commit()
    if failure == "rotated":
        monkeypatch.setenv(value["token_env"], "rotated-project-credential-after-queue")
    executor.run_job(repo.scope, data[3], run_id, sha)
    session.expire_all()
    assert session.get(Task, data[3]).status == "EXECUTION_FAILED"
    run = session.scalar(select(Run).where(Run.run_id == run_id))
    assert run.state == "failed" and not run.is_active
    assert (root / "readme.md").read_text() == (
        "base\napproved change\n" if failure == "publish" else "base\n"
    )


def test_same_clone_cannot_be_registered_to_two_scopes(setup, monkeypatch):
    data, _, value = setup
    other = {**value, "id": "other", "project_id": value["project_id"] + 1}
    monkeypatch.setenv(executor.PROFILE_ENV, json.dumps([value, other]))
    with pytest.raises(executor.ExecutionConflict):
        executor.profiles(data[0].scope)


def test_lock_never_deletes_foreign_lock(setup):
    _, root, _ = setup
    path = root / ".git" / "mywave-scoped-execution.lock"
    with executor.locked(root, "owner"):
        with pytest.raises(executor.ExecutionConflict):
            with executor.locked(root, "other"):
                pass
        path.write_text("replaced-owner")
    assert path.read_text() == "replaced-owner"


def test_validation_docker_has_no_network_credentials_or_production_mounts(
    setup, monkeypatch
):
    _, root, value = setup
    original = executor.command
    observed = []

    def command(args, **kwargs):
        if args[:3] == ["docker", "image", "inspect"]:
            return (
                b'[{"Config":{"Env":[],"Labels":{"mywave.scoped-validation":"true"}}}]'
            )
        if args[0] == "docker":
            observed.append(args)
            mount = args[args.index("--mount") + 1]
            path = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            assert (path / "readme.md").read_text() == "base\napproved change\n"
            assert not (path / ".git").exists()
            return b"1 passed"
        return original(args, **kwargs)

    monkeypatch.setattr(executor, "command", command)
    real_run = subprocess.run
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: (
            subprocess.CompletedProcess(args, 1, stdout=b"")
            if args[:2] == ["docker", "inspect"]
            else real_run(args, **kwargs)
        ),
    )
    executor.sandbox(root, value, PATCH.encode())
    args = observed[0]
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--user") + 1] == "65534:65534"
    assert "--read-only" in args and "--cap-drop" in args and "--pids-limit" in args
    assert not any("GH_TOKEN" in arg or "WORKSPACE_KEY" in arg for arg in args)


@pytest.mark.parametrize(
    "failure", ["credential_image", "unqualified_image", "source_changed"]
)
def test_sandbox_rejects_unsafe_image_and_source_changes(setup, monkeypatch, failure):
    _, root, value = setup
    original = executor.command

    def command(args, **kwargs):
        if args[:3] == ["docker", "image", "inspect"]:
            config = {"Env": [], "Labels": {"mywave.scoped-validation": "true"}}
            if failure == "credential_image":
                config["Env"] = ["DATABASE_URL=postgresql://private.invalid/db"]
            if failure == "unqualified_image":
                config["Labels"] = {}
            return json.dumps([{"Config": config}]).encode()
        if args[:2] == ["docker", "run"]:
            mount = args[args.index("--mount") + 1]
            path = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            (path / "readme.md").write_text("Modified by tests")
            return b""
        return original(args, **kwargs)

    monkeypatch.setattr(executor, "command", command)
    real_run = subprocess.run
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: (
            subprocess.CompletedProcess(args, 1, stdout=b"")
            if args[:2] == ["docker", "inspect"]
            else real_run(args, **kwargs)
        ),
    )
    with pytest.raises(executor.ExecutionConflict):
        executor.sandbox(root, value, PATCH.encode())
    assert (root / "readme.md").read_text() == "base\n"


def test_worker_filters_profiles_before_queue_limit(setup, session, monkeypatch):
    from app.workspaces import patch_worker

    data, _, _, sha = ready(setup, session)
    for i in range(101):
        task = Task(
            workspace_id=data[1],
            project_id=data[2],
            status="EXECUTING",
            owner_text="Another worker",
        )
        session.add(task)
        session.flush()
        session.add(
            Run(
                run_id="other-" + str(i),
                task_id=task.id,
                orchestrator="scoped_patch_v1",
                source="scoped_project",
                state="running",
                phase="queued",
                current_step="another-profile",
                is_active=True,
                message=json.dumps(
                    {"principal_id": "alice", "proposal_sha256": "f" * 64}
                ),
            )
        )
    session.commit()
    queued = executor.start(data[0], data[3], sha)
    observed = []
    monkeypatch.setattr(patch_worker, "run_job", lambda *args: observed.append(args))
    result = patch_worker.run_once()
    assert result["processed"] and result["run_id"] == queued
    assert observed[0][2] == queued
    assert patch_worker.run_once() == {"processed": False}
    session.expire_all()
    assert all(
        run.phase == "queued"
        for run in session.scalars(
            select(Run).where(Run.current_step == "another-profile")
        )
    )
