"""Trusted-host smoke: real Docker tests and Git commits; simulated GitHub only.

Requires only SQLAlchemy in a dedicated host QA venv. Does not mount the Docker
socket into a container or read production credentials, database or source.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(args.root)
    assert root.parent == Path("/opt/mywave/ai-team-runtime") and root.name.startswith(
        "scoped-worker-qa-"
    )
    assert (
        root.is_dir() and not root.is_symlink() and root.stat().st_uid == os.geteuid()
    )
    assert not root.stat().st_mode & 0o077
    assert re.fullmatch("sha256:[0-9a-f]{64}", args.image)

    def docker(*parts):
        return subprocess.check_output(["docker", *parts], stderr=subprocess.PIPE)

    before = json.loads(docker("inspect", "ai-team-app-1"))[0]
    production = (before["Id"], before["Image"])
    with tempfile.TemporaryDirectory(prefix="work-", dir=root) as temporary:
        work = Path(temporary)
        os.environ.update(
            DATABASE_URL="sqlite:///" + str(work / "qa.sqlite"),
            OWNER_API_KEY="synthetic-host-qa-only",
            WORKSPACE_PATCH_EXECUTION_ENABLED="true",
            WORKSPACE_PATCH_WORKER_ENABLED="true",
            WORKSPACE_EXECUTION_TOKEN_TEST="synthetic-project-worker-credential",
            EXECUTION_ALLOWED_ROOTS_JSON="[]",
            ARTIFACTS_DIR=str(work / "artifacts"),
        )
        from sqlalchemy.orm import Session
        from app.storage.models import (
            Base,
            Workspace,
            Project,
            Task,
            ProjectAccessGrant,
            WorkspaceMembership,
        )
        from app.storage.repositories import get_engine
        from app.workspaces.access import Scope, ScopedRepository
        from app.workspaces import patch_executor as executor
        from app.workspaces.patch_worker import run_once

        engine = get_engine()
        assert engine.url.get_backend_name() == "sqlite"
        Base.metadata.create_all(engine)
        clone = work / "clones" / "repo"
        clone.mkdir(parents=True)

        def git(*parts):
            return subprocess.check_output(
                ["git", "-C", str(clone), *parts], stderr=subprocess.PIPE
            )

        git("init")
        git("config", "user.name", "Scoped Docker QA")
        git("config", "user.email", "qa@example.invalid")
        git("config", "core.autocrlf", "false")
        git("remote", "add", "origin", "https://github.com/example/scoped.git")
        (clone / "readme.md").write_text("base\n")
        (clone / "tests").mkdir()
        (clone / "tests" / "test_real.py").write_text(
            """import os, socket
from pathlib import Path
import pytest
def test_approved_source():
    assert Path("readme.md").read_text() == "base\\napproved change\\n"
def test_no_secrets_or_repository_metadata():
    assert not Path(".git").exists()
    assert not any(k in os.environ for k in ("GH_TOKEN", "GITHUB_TOKEN", "WORKSPACE_EXECUTION_TOKEN_TEST"))
def test_no_network():
    with pytest.raises(OSError):
        socket.create_connection(("198.51.100.1", 443), timeout=0.2)
"""
        )
        git("add", ".")
        git("commit", "-m", "QA source")
        with Session(engine) as session:
            workspace = Workspace(
                slug="qa", name="Synthetic QA", kind="MYWAVE", owner_id="qa"
            )
            session.add(workspace)
            session.flush()
            project = Project(
                slug="qa", name="Synthetic project", workspace_id=workspace.id
            )
            session.add(project)
            session.flush()
            session.add_all(
                [
                    WorkspaceMembership(
                        workspace_id=workspace.id, principal_id="qa", role="owner"
                    ),
                    ProjectAccessGrant(
                        project_id=project.id, principal_id="qa", role="owner"
                    ),
                ]
            )
            session.commit()
            scope = Scope("qa", workspace.id, project.id)
        os.environ["WORKSPACE_PATCH_ROOTS_JSON"] = json.dumps([str(clone.parent)])
        os.environ[executor.PROFILE_ENV] = json.dumps(
            [
                {
                    "id": "qa",
                    "workspace_id": scope.workspace_id,
                    "project_id": scope.project_id,
                    "workspace_path": str(clone),
                    "repository": "example/scoped",
                    "validation_image": args.image,
                    "token_env": "WORKSPACE_EXECUTION_TOKEN_TEST",
                }
            ]
        )
        observed, containers = [], []
        original = executor.command

        def command(parts, **kwargs):
            if parts[:2] == ["gh", "api"]:
                observed.append("github_permission_simulated")
                return b"true\n"
            if parts[:3] == ["gh", "pr", "create"]:
                observed.append("pr_simulated")
                return b"https://github.com/example/scoped/pull/1\n"
            if parts[0] == "git" and "push" in parts:
                observed.append("push_simulated")
                return b""
            if parts[:2] == ["docker", "run"]:
                containers.append(parts[parts.index("--name") + 1])
            return original(parts, **kwargs)

        executor.command = command

        def mission(patch):
            with Session(engine) as session:
                task = Task(
                    workspace_id=scope.workspace_id,
                    project_id=scope.project_id,
                    owner_text="Synthetic patch smoke",
                )
                session.add(task)
                session.commit()
                tid = task.id
                repo = ScopedRepository(session, scope)
                prepared = executor.prepare(repo, tid, "qa", patch)
                sha = prepared["proposal_sha256"]
                executor.decide(repo, tid, sha, "approve")
                executor.start(repo, tid, sha)
            assert run_once()["processed"]
            with Session(engine) as session:
                return executor.snapshot(ScopedRepository(session, scope), tid)

        good = "diff --git a/readme.md b/readme.md\n--- a/readme.md\n+++ b/readme.md\n@@ -1 +1,2 @@\n base\n+approved change\n"
        result = mission(good)
        assert (
            result["status"] == "APPROVED_WAIT_MERGE"
            and result["run"]["state"] == "completed"
        )
        head = git("rev-parse", "HEAD")
        published = list(observed)
        bad = "diff --git a/readme.md b/readme.md\n--- a/readme.md\n+++ b/readme.md\n@@ -1,2 +1,2 @@\n base\n-approved change\n+bad change\n"
        failed = mission(bad)
        assert (
            failed["status"] == "EXECUTION_FAILED"
            and failed["run"]["state"] == "failed"
        )
        assert (
            git("rev-parse", "HEAD") == head
            and (clone / "readme.md").read_text() == "base\napproved change\n"
        )
        assert observed.count("pr_simulated") == published.count("pr_simulated") == 1
        assert len(containers) == 2
        for name in containers:
            assert (
                subprocess.run(
                    ["docker", "container", "inspect", name], capture_output=True
                ).returncode
                != 0
            )
        assert run_once() == {"processed": False}
        engine.dispose()
    after = json.loads(docker("inspect", "ai-team-app-1"))[0]
    assert (after["Id"], after["Image"]) == production and after["State"]["Health"][
        "Status"
    ] == "healthy"
    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "real_docker_validation": "passed",
        "positive_tests": 3,
        "failing_tests_block_commit_and_publication": True,
        "real_git_commit": "passed",
        "github_permission_push_and_pr": "simulated_no_network",
        "cleanup": "passed",
        "production_changed": False,
        "business_outcome_verified": False,
    }
    (root / "host-smoke.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
