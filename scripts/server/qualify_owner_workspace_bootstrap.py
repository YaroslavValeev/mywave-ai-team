"""Isolated operator qualification; only production operation is a read-only dump."""

import hashlib
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

IMAGE = "sha256:ddb4d20a8dc980f81abb4033f0eba75eb24073250583d2d94313e78cdd77d3f1"
PG_IMAGE = "sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f"


def run(args, *, data=None, timeout=180):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("Qualification command failed; private output withheld")
    return result.stdout


def inspect(name):
    return json.loads(run(["docker", "inspect", name]))[0]


def main():
    os.umask(0o077)
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/server/bootstrap_mywave_club_box.py").read_bytes()
    assert inspect("ai-team-app-1")["Image"] == IMAGE
    assert inspect("ai-team-postgres-1")["Image"] == PG_IMAGE
    ident = uuid.uuid4().hex
    pg = "owner-bootstrap-qa-" + ident
    proof = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "image_id": IMAGE,
        "script_sha256": hashlib.sha256(script).hexdigest(),
        "production_access_changed": False,
    }

    def sql(query, database="restore_drill"):
        return (
            run(
                [
                    "docker",
                    "exec",
                    pg,
                    "psql",
                    "-X",
                    "-U",
                    "drill",
                    "-d",
                    database,
                    "-At",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    query,
                ]
            )
            .decode()
            .strip()
        )

    def fingerprints():
        return {
            table: sql(
                "SELECT md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'null')) FROM "
                + table
                + " t WHERE workspace_id IS NULL"
            )
            for table in ("projects", "tasks", "memory_entries")
        }

    def app(
        arguments, database="restore_drill", data=script, mount=False, pg_tests=False
    ):
        name = "owner-bootstrap-app-" + uuid.uuid4().hex
        args = [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "-i",
            "--name",
            name,
            "--label",
            "mywave.owner-bootstrap-qa=" + ident,
            "--network",
            "container:" + pg,
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=64m",
            "--memory",
            "384m",
            "--memory-swap",
            "384m",
            "--cpus",
            "0.5",
            "--pids-limit",
            "128",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "PYTHONPATH=/app",
            "-e",
            "DATABASE_URL=postgresql+psycopg2://drill@127.0.0.1:5432/" + database,
            "-e",
            "WORKSPACE_ACCESS_ENABLED=false",
            "-e",
            "WORKSPACE_OWNER_PRINCIPAL_ID=",
            "-e",
            "WORKSPACE_PRINCIPAL_BINDINGS_JSON=[]",
            "-e",
            "TELEGRAM_POLLING_ENABLED=false",
        ]
        if mount:
            args += [
                "--mount",
                "type=bind,source=" + str(root) + ",target=/qualification,readonly",
                "--workdir",
                "/qualification",
            ]
        if pg_tests:
            args += [
                "-e",
                "BOOTSTRAP_TEST_DATABASE_URL=postgresql+psycopg2://drill@127.0.0.1:5432/bootstrap_qa",
            ]
        return run(args + ["--entrypoint", "python", IMAGE, *arguments], data=data)

    try:
        pg_env = dict(
            v.split("=", 1)
            for v in inspect("ai-team-postgres-1")["Config"]["Env"]
            if "=" in v
        )
        backup = root / "production-009.dump"
        with backup.open("xb") as stream:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "ai-team-postgres-1",
                    "pg_dump",
                    "-U",
                    pg_env["POSTGRES_USER"],
                    "-d",
                    pg_env["POSTGRES_DB"],
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                ],
                stdout=stream,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        assert result.returncode == 0 and backup.stat().st_size > 0
        proof["backup"] = str(backup)
        proof["backup_sha256"] = hashlib.sha256(backup.read_bytes()).hexdigest()
        run(
            [
                "docker",
                "run",
                "-d",
                "--pull",
                "never",
                "--name",
                pg,
                "--label",
                "mywave.owner-bootstrap-qa=" + ident,
                "--network",
                "none",
                "--memory",
                "384m",
                "--memory-swap",
                "384m",
                "--cpus",
                "0.5",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=256m",
                "-e",
                "POSTGRES_USER=drill",
                "-e",
                "POSTGRES_DB=restore_drill",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                PG_IMAGE,
            ]
        )
        for _ in range(60):
            result = subprocess.run(
                ["docker", "exec", pg, "pg_isready", "-h", "127.0.0.1", "-U", "drill"],
                capture_output=True,
            )
            if result.returncode == 0:
                break
            time.sleep(2)
        else:
            raise RuntimeError("Isolated PostgreSQL readiness timed out")
        run(
            [
                "docker",
                "exec",
                "-i",
                pg,
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "-U",
                "drill",
                "-d",
                "restore_drill",
            ],
            data=backup.read_bytes(),
        )
        assert sql("SELECT version_num FROM alembic_version") == "009"
        assert sql("SELECT count(*) FROM tasks WHERE id=38 AND status='DONE'") == "1"
        assert (
            sql("SELECT count(*) FROM tasks WHERE id=39 AND status='WAIT_OWNER'") == "1"
        )
        proof["restore_009"] = "passed"
        before = fingerprints()
        preview = app(["-"]).decode()
        (root / "qa-preview.log").write_text(preview)
        plan = json.loads(preview.split("WORKSPACE_BOOTSTRAP_PREVIEW_PASSED")[0])
        assert plan["changed"] is False and plan["action"] == "would_create"
        approval = plan["plan_sha256"]
        for expected in (True, False):
            output = app(["-", "--execute", "--owner-approved-plan", approval]).decode()
            result = json.loads(output.split("WORKSPACE_BOOTSTRAP_APPLIED")[0])
            assert result["changed"] is expected
        assert fingerprints() == before
        assert (
            sql(
                "SELECT count(*) FROM audit_events WHERE event_type='workspace_bootstrap_approved'"
            )
            == "1"
        )
        proof["restored_copy_bootstrap"] = {
            "plan_sha256": approval,
            "preview_read_only": True,
            "created_once": True,
            "repeat_changed": False,
            "legacy_fingerprints_preserved": True,
        }
        run(["docker", "exec", pg, "createdb", "-U", "drill", "bootstrap_qa"])
        for label, pg_tests in (("sqlite", False), ("postgres", True)):
            output = app(
                [
                    "-m",
                    "pytest",
                    "tests/isolated/test_owner_workspace_bootstrap.py",
                    "--confcutdir=tests/isolated",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                ],
                database="bootstrap_qa",
                data=None,
                mount=True,
                pg_tests=pg_tests,
            ).decode()
            (root / (label + "-tests.log")).write_text(output)
            proof[label + "_tests"] = output.strip().splitlines()[-1]
        # Production preview only; approval is deliberately not supplied here.
        live = run(
            ["docker", "exec", "-i", "ai-team-app-1", "python", "-"], data=script
        ).decode()
        live_plan = json.loads(live.split("WORKSPACE_BOOTSTRAP_PREVIEW_PASSED")[0])
        assert (
            live_plan["changed"] is False
            and live_plan["action"] == "would_create"
            and live_plan["plan_sha256"] == approval
        )
        (root / "production-preview.json").write_text(json.dumps(live_plan, indent=2))
        proof["production_preview"] = "passed_without_writes"
        proof["result"] = "passed"
    finally:
        ids = (
            run(
                [
                    "docker",
                    "ps",
                    "-aq",
                    "--filter",
                    "label=mywave.owner-bootstrap-qa=" + ident,
                ]
            )
            .decode()
            .split()
        )
        for name in ids:
            if (
                inspect(name)["Config"]["Labels"].get("mywave.owner-bootstrap-qa")
                != ident
            ):
                raise RuntimeError("Unexpected cleanup target; left untouched")
            run(["docker", "rm", "-f", "-v", name])
        proof["cleanup"] = "passed"
        (root / "qualification.json").write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof, indent=2), flush=True)


if __name__ == "__main__":
    main()
