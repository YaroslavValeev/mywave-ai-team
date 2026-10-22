"""Isolated candidate build, PostgreSQL tests and live HTTP smoke; no production rollout."""

import argparse
from datetime import datetime, timezone
import re
import shutil
import stat
import tempfile
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import uuid


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    source = args.source_sha
    if not re.fullmatch("[0-9a-f]{40}", source):
        raise RuntimeError("Full source SHA required")
    runtime = Path("/opt/mywave/ai-team-runtime")
    repository = Path("/opt/mywave/ai-team")
    if not args.execute:
        print(
            json.dumps(
                {
                    "source_sha": source,
                    "mode": "preview",
                    "production_changed": False,
                    "isolated_postgresql": True,
                    "candidate_build": True,
                },
                indent=2,
            )
        )
        return
    assert os.geteuid() == 0
    info = runtime.lstat()
    assert (
        not runtime.is_symlink()
        and info.st_uid == 0
        and not stat.S_IMODE(info.st_mode) & 0o022
    )
    assert shutil.disk_usage(runtime).free >= 1024**3, "At least 1 GiB free required"
    assert (
        subprocess.check_output(
            ["git", "-C", str(repository), "rev-parse", source + "^{commit}"], text=True
        ).strip()
        == source
    )
    root = Path(
        tempfile.mkdtemp(prefix="project-console-qa-" + source[:12] + "-", dir=runtime)
    )
    print("EVIDENCE_DIRECTORY=" + str(root), flush=True)
    (root / "source.tar.gz").write_bytes(
        subprocess.check_output(
            ["git", "-C", str(repository), "archive", "--format=tar.gz", source]
        )
    )
    (root / "live-smoke.py").write_bytes(
        subprocess.check_output(
            [
                "git",
                "-C",
                str(repository),
                "show",
                source + ":tests/isolated/project_console_live_smoke.py",
            ]
        )
    )
    base_image = (
        "sha256:ddb4d20a8dc980f81abb4033f0eba75eb24073250583d2d94313e78cdd77d3f1"
    )
    ident = uuid.uuid4().hex
    tag = "ai-team-console-qa:" + source[:12] + "-" + ident[:8]
    pg = "console-qa-pg-" + ident
    runner = "console-qa-run-" + ident
    db = "ai_team_workspace_qa_console_" + ident[:12]
    report = {
        "source_sha": source,
        "production_changed": False,
        "synthetic_credentials_only": True,
    }

    def run(args, *, data=None, timeout=180, log=None):
        result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
        if log:
            (root / log).write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("QA command failed" + (": " + log if log else ""))
        return result.stdout

    def inspect(name):
        return json.loads(run(["docker", "inspect", name]))[0]

    before = inspect("ai-team-app-1")
    assert (
        before["Image"] == base_image
        and before["State"]["Health"]["Status"] == "healthy"
    )
    pg_image = inspect("ai-team-postgres-1")["Image"]
    base_env = json.loads(run(["docker", "image", "inspect", base_image]))[0]["Config"][
        "Env"
    ]
    assert not any(
        v.split("=", 1)[0]
        in {"OWNER_API_KEY", "GH_TOKEN", "GITHUB_TOKEN", "WORKSPACE_KEY_CLUB_BOX_OWNER"}
        for v in base_env
    )
    context = root / "build"
    context.mkdir(mode=0o700)
    src = context / "src"
    src.mkdir(mode=0o700)
    with tarfile.open(root / "source.tar.gz", "r:gz") as archive:
        for item in archive.getmembers():
            path = Path(item.name)
            assert (
                not path.is_absolute()
                and ".." not in path.parts
                and not item.issym()
                and not item.islnk()
            )
        archive.extractall(src, filter="data")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (context / "Dockerfile").write_text(
        f"FROM {base_image}\nCOPY src/ /app/\nENV APP_COMMIT_SHA={source} APP_VERSION=qa-{source[:12]} APP_BUILD_TIMESTAMP={stamp} APP_ENVIRONMENT=qualification\n"
    )
    try:
        run(
            [
                "docker",
                "build",
                "--pull=false",
                "--network",
                "none",
                "--label",
                "mywave.console-qa=" + ident,
                "--label",
                "org.opencontainers.image.revision=" + source,
                "-t",
                tag,
                str(context),
            ],
            timeout=300,
            log="build.log",
        )
        report["image_id"] = json.loads(run(["docker", "image", "inspect", tag]))[0][
            "Id"
        ]
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
                "mywave.console-qa=" + ident,
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
                "POSTGRES_USER=qa",
                "-e",
                "POSTGRES_DB=qa",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                pg_image,
            ]
        )
        for _ in range(60):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    pg,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "qa",
                    "-d",
                    "qa",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Temporary PostgreSQL unavailable")
        run(["docker", "exec", pg, "createdb", "-U", "qa", db])
        url = "postgresql+psycopg2://qa@127.0.0.1:5432/" + db
        flags = [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--name",
            runner,
            "--label",
            "mywave.console-qa=" + ident,
            "--network",
            "container:" + pg,
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=128m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "512m",
            "--memory-swap",
            "512m",
            "--cpus",
            "0.75",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "PYTHONPATH=/app:/app/tests/isolated:/app/packages/shared-core:/app/packages/agents-http-client",
            "-e",
            "OWNER_API_KEY=synthetic-docker-console-legacy",
            "-e",
            "WORKSPACE_TEST_DATABASE_URL=" + url,
            "-e",
            "TELEGRAM_POLLING_ENABLED=false",
            "-e",
            "TELEGRAM_PROACTIVE_NOTIFY_ENABLED=false",
            "-e",
            "ORCHESTRATION_ENGINE=rule_based",
            "--entrypoint",
            "python",
        ]
        result = run(
            flags
            + [
                tag,
                "-m",
                "pytest",
                "tests/isolated",
                "--confcutdir=tests/isolated",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            timeout=600,
            log="tests.log",
        ).decode()
        report["docker_tests"] = next(
            line for line in reversed(result.splitlines()) if " passed" in line
        )
        run(["docker", "exec", pg, "dropdb", "-U", "qa", db])
        run(["docker", "exec", pg, "createdb", "-U", "qa", db])
        bindings = '[{"principal_id":"qa-owner","key_env":"WORKSPACE_KEY_QA"}]'
        smoke_flags = flags[:-2] + [
            "-e",
            "DATABASE_URL=" + url,
            "-e",
            "WORKSPACE_ACCESS_ENABLED=true",
            "-e",
            "WORKSPACE_OWNER_PRINCIPAL_ID=",
            "-e",
            "WORKSPACE_PRINCIPAL_BINDINGS_JSON=" + bindings,
            "-e",
            "WORKSPACE_KEY_QA=synthetic-docker-console-project",
            "-e",
            "ARTIFACTS_DIR=/tmp/artifacts",
            "--mount",
            "type=bind,source="
            + str(root / "live-smoke.py")
            + ",target=/qualification/live-smoke.py,readonly",
            "--entrypoint",
            "python",
        ]
        report["live_smoke"] = json.loads(
            run(
                smoke_flags + [tag, "/qualification/live-smoke.py"],
                timeout=150,
                log="live-smoke.log",
            )
        )
        after = inspect("ai-team-app-1")
        assert (
            after["Id"] == before["Id"]
            and after["Image"] == before["Image"]
            and after["State"]["Health"]["Status"] == "healthy"
        )
        report["production_container_unchanged"] = True
        report["result"] = "passed"
    finally:
        for name in (runner, pg):
            data = subprocess.run(["docker", "inspect", name], capture_output=True)
            if data.returncode == 0:
                current = json.loads(data.stdout)[0]
                assert current["Config"]["Labels"].get("mywave.console-qa") == ident
                run(["docker", "rm", "-f", "-v", name], log="cleanup.log")
        report["cleanup"] = "passed"
        (root / "qualification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
