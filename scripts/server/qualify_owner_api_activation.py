"""Isolated Compose/auth rehearsal. Uses a restored backup and synthetic keys only."""

import hashlib
import importlib.util
import json
import os
import secrets
import subprocess
import time
import uuid
from pathlib import Path
from types import SimpleNamespace


def run(args, *, data=None, timeout=180):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        (Path(__file__).resolve().parents[2] / "failure.log").write_bytes(
            result.stdout + result.stderr
        )
        raise RuntimeError("Qualification command failed; private output withheld")
    return result.stdout


def inspect(name):
    return json.loads(run(["docker", "inspect", name]))[0]


def main():
    os.umask(0o077)
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "activation", root / "scripts/server/activate_club_box_owner.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert inspect("ai-team-app-1")["Image"] == module.IMAGE
    backup_root = Path("/opt/mywave/ai-team-runtime/owner-bootstrap-20261022-v1")
    proof = json.loads((backup_root / "production-verification.json").read_text())
    backup = backup_root / "post-bootstrap-009.dump"
    assert (
        proof["post_bootstrap_restore"] == "passed"
        and hashlib.sha256(backup.read_bytes()).hexdigest()
        == proof["post_bootstrap_backup_sha256"]
    )
    ident = uuid.uuid4().hex
    project = "owner-auth-qa-" + ident
    pg = project + "-pg"
    app = project + "-app"
    db = "ai_team_workspace_qa_auth_" + ident[:12]
    pg_image = inspect("ai-team-postgres-1")["Image"]
    shared_file, owner_file = root / "__qa_shared.env", root / "__qa_owner.env"
    base_file, enabled_file = root / "__qa_base.json", root / "__qa_enabled.json"
    report = {
        "production_changed": False,
        "synthetic_credentials_only": True,
        "image_id": module.IMAGE,
    }

    def compose(*args, enabled=True):
        flags = ["-f", str(base_file)] + (["-f", str(enabled_file)] if enabled else [])
        return run(["docker", "compose", "-p", project, *flags, *args])

    def wait():
        for _ in range(60):
            current = inspect(app)
            if current["State"].get("Health", {}).get("Status") == "healthy":
                return
            if current["State"]["Status"] == "exited":
                raise RuntimeError("Isolated app exited")
            time.sleep(2)
        raise RuntimeError("Isolated app readiness timed out")

    try:
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
                "mywave.owner-auth-qa=" + ident,
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
                pg_image,
            ]
        )
        for _ in range(60):
            if (
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        pg,
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "drill",
                    ],
                    capture_output=True,
                ).returncode
                == 0
            ):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Isolated PostgreSQL did not become ready")
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
        run(["docker", "exec", pg, "createdb", "-U", "drill", db])
        qa_url = "postgresql+psycopg2://drill@127.0.0.1:5432/" + db
        tests = run(
            [
                "docker",
                "run",
                "--rm",
                "--pull",
                "never",
                "--name",
                project + "-tests",
                "--label",
                "mywave.owner-auth-qa=" + ident,
                "--network",
                "container:" + pg,
                "--read-only",
                "--tmpfs",
                "/tmp:rw,size=128m",
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
                "--mount",
                "type=bind,source=" + str(root) + ",target=/qualification,readonly",
                "--workdir",
                "/qualification",
                "-e",
                "PYTHONDONTWRITEBYTECODE=1",
                "-e",
                "PYTHONPATH=/app:/app/tests/isolated:/app/packages/shared-core:/app/packages/agents-http-client",
                "-e",
                "DATABASE_URL=" + qa_url,
                "-e",
                "WORKSPACE_TEST_DATABASE_URL=" + qa_url,
                "-e",
                "TELEGRAM_POLLING_ENABLED=false",
                "--entrypoint",
                "python",
                module.IMAGE,
                "-m",
                "pytest",
                "tests/isolated/test_owner_api_activation.py",
                "--confcutdir=tests/isolated",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            timeout=240,
        ).decode()
        (root / "tests.log").write_text(tests)
        report["docker_tests"] = tests.strip().splitlines()[-1]
        shared_file.write_text("OWNER_API_KEY=" + secrets.token_urlsafe(48) + "\n")
        owner_file.write_text(module.KEY_ENV + "=" + secrets.token_urlsafe(48) + "\n")
        for path in (shared_file, owner_file):
            path.chmod(0o600)
        base = {
            "services": {
                "app": {
                    "image": module.IMAGE,
                    "container_name": app,
                    "labels": {"mywave.owner-auth-qa": ident},
                    "network_mode": "container:" + pg,
                    "read_only": True,
                    "tmpfs": ["/tmp:rw,size=64m"],
                    "mem_limit": "384m",
                    "memswap_limit": "384m",
                    "cpus": 0.5,
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "env_file": [str(shared_file)],
                    "environment": {
                        "DATABASE_URL": "postgresql+psycopg2://drill@127.0.0.1:5432/restore_drill",
                        "WORKSPACE_ACCESS_ENABLED": "false",
                        "WORKSPACE_OWNER_PRINCIPAL_ID": "",
                        "WORKSPACE_PRINCIPAL_BINDINGS_JSON": "[]",
                        "TELEGRAM_POLLING_ENABLED": "false",
                        "TELEGRAM_PROACTIVE_NOTIFY_ENABLED": "false",
                        "ARTIFACTS_DIR": "/tmp/artifacts",
                        "ORCHESTRATION_ENGINE": "rule_based",
                    },
                    "command": ["python", "-m", "app.main"],
                    "healthcheck": {
                        "test": [
                            "CMD",
                            "python",
                            "-c",
                            "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3)",
                        ],
                        "interval": "3s",
                        "timeout": "5s",
                        "retries": 12,
                    },
                },
                "observer": {
                    "image": module.IMAGE,
                    "env_file": [str(shared_file)],
                    "profiles": ["disabled"],
                },
            }
        }
        module.KEY_FILE = (
            owner_file  # Pure renderer test; never points QA at a real key.
        )
        base_file.write_text(json.dumps(base))
        # Render an override, not a second complete base: security_opt sequences
        # would otherwise be concatenated and fail Compose duplicate validation.
        enabled_file.write_text(
            json.dumps(module.render({"services": {"app": {"image": module.IMAGE}}}))
        )
        config = json.loads(compose("--profile", "*", "config", "--format", "json"))
        assert module.KEY_ENV in config["services"]["app"]["environment"]
        assert module.KEY_ENV not in config["services"]["observer"]["environment"]
        compose("up", "-d", "--no-build", "--no-deps", "--pull", "never", "app")
        wait()
        ops = SimpleNamespace(APP=app, command=run)
        statuses = {
            mode: module.probe(ops, mode)["status"]
            for mode in ("dedicated", "none", "wrong", "shared")
        }
        assert statuses == {"dedicated": 200, "none": 403, "wrong": 403, "shared": 403}
        assert module.probe(ops, workspace=2)["status"] == 403
        assert module.probe(ops, project=1)["status"] == 403
        assert module.probe(ops, suffix="overview")["status"] == 200

        def sql(query):
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
                        "restore_drill",
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

        sql("UPDATE project_access_grants SET revoked_at=now() WHERE project_id=2")
        assert module.probe(ops)["status"] == 403
        sql("UPDATE project_access_grants SET revoked_at=NULL WHERE project_id=2")
        assert module.probe(ops)["status"] == 200
        compose(
            "up",
            "-d",
            "--no-build",
            "--no-deps",
            "--pull",
            "never",
            "--force-recreate",
            "app",
            enabled=False,
        )
        wait()
        assert module.probe(ops, "none")["status"] == 404
        env = dict(v.split("=", 1) for v in inspect(app)["Config"]["Env"] if "=" in v)
        assert module.KEY_ENV not in env and inspect(app)["Image"] == module.IMAGE
        report.update(
            {
                "auth_statuses": statuses,
                "cross_scope_denied": True,
                "revocation_checked": True,
                "same_image_disable_rehearsed": True,
                "observer_secret_absent": True,
                "result": "passed",
            }
        )
    finally:
        ids = (
            run(
                [
                    "docker",
                    "ps",
                    "-aq",
                    "--filter",
                    "label=mywave.owner-auth-qa=" + ident,
                ]
            )
            .decode()
            .split()
        )
        for name in ids:
            assert (
                inspect(name)["Config"]["Labels"].get("mywave.owner-auth-qa") == ident
            )
            run(["docker", "rm", "-f", "-v", name])
        networks = (
            run(
                [
                    "docker",
                    "network",
                    "ls",
                    "-q",
                    "--filter",
                    "label=com.docker.compose.project=" + project,
                ]
            )
            .decode()
            .split()
        )
        for network in networks:
            data = json.loads(run(["docker", "network", "inspect", network]))[0]
            assert data["Labels"].get("com.docker.compose.project") == project
            run(["docker", "network", "rm", network])
        for path in (shared_file, owner_file):
            path.unlink(missing_ok=True)
        report["cleanup"] = "passed"
        (root / "qualification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
