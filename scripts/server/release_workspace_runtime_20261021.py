"""Pinned workspace rollout; default checks only. No automatic schema downgrade."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/mywave/ai-team")
RUNTIME = Path("/opt/mywave/ai-team-runtime")
APP = "ai-team-app-1"
PG = "ai-team-postgres-1"
SOURCE = "b2a11824342f7b7921bcb3d84dcdc8913fa8e86b"
IMAGE = "sha256:ddb4d20a8dc980f81abb4033f0eba75eb24073250583d2d94313e78cdd77d3f1"
OLD_SOURCE = "20476d9fd5a8df89dd9ae33c1c61957569c39307"
OLD_IMAGE = "sha256:f85bdfc8aa43952d074521e295c312da97bda74ebc77435d6a2feece34415dc1"
COMPOSE = [
    ROOT / "docker-compose.yml",
    ROOT / "docker-compose.server-full.yml",
    RUNTIME / "candidate.yml",
]
HASHES = [
    "7d8a18719bf53fb0e3a094f14426dc308dc0b4672a4f5730de5d999e37bc3219",
    "c19db2e3f822101559a24343a48ad17ede2f3070e8c5a3bf4f17b5113610885b",
    "e99dec658c296baf0a0ad2c4bda37cb25c4576cf0f659e7bb01a1318007ac770",
]
DB_BACKUP = RUNTIME / "backups/pre-workspace-20261021T200411Z-9Iq8Nj"
FILES_BACKUP = RUNTIME / "backups/release-files-20261021T201458Z-5Yb10V"
MIGRATION_PROOF = DB_BACKUP / "migration-check-Vcs9K0/result.txt"
QUALIFICATION = (
    RUNTIME
    / "workspace-qa-20261019/ai-team-workspace-qa-7a9331a7ba29411d989650bc5c322f37/qualification.json"
)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def command(args, data=None, timeout=120):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    require(result.returncode == 0, "Command failed; private command output withheld")
    return result.stdout


def inspect(name):
    return json.loads(command(["docker", "inspect", name]))[0]


def environment(item):
    return dict(
        value.split("=", 1) for value in item["Config"].get("Env", []) if "=" in value
    )


def compose(*args):
    flags = [part for path in COMPOSE for part in ("-f", str(path))]
    return command(
        ["docker", "compose", "--project-directory", str(ROOT), *flags, *args],
        timeout=180,
    )


def api(path):
    code = (
        "import json,os,urllib.request; r=urllib.request.Request("
        + repr("http://127.0.0.1:8080/api" + path)
        + ',headers={"X-API-Key":os.environ["OWNER_API_KEY"]}); '
        + "print(json.dumps(json.load(urllib.request.urlopen(r,timeout=20))))"
    )
    return json.loads(
        command(["docker", "exec", APP, "python", "-c", code], timeout=35)
    )


def sql(query):
    env = environment(inspect(PG))
    return (
        command(
            [
                "docker",
                "exec",
                PG,
                "psql",
                "-X",
                "-U",
                env["POSTGRES_USER"],
                "-d",
                env.get("POSTGRES_DB", env["POSTGRES_USER"]),
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


def db_state():
    version = sql("SELECT version_num FROM alembic_version;")
    active = int(
        sql(
            "SELECT (SELECT count(*) FROM runs WHERE is_active=true) + (SELECT count(*) FROM tasks WHERE status IN ('IN_PIPELINE','IN_ROUNDTABLE','IN_COURT','EXECUTING','VALIDATING'));"
        )
    )
    scoped = sql("SELECT to_regclass('public.workspaces') IS NOT NULL;") == "t"
    count = 0
    if scoped:
        count = int(
            sql(
                "SELECT (SELECT count(*) FROM workspaces) + (SELECT count(*) FROM workspace_memberships) + (SELECT count(*) FROM project_access_grants) + (SELECT count(*) FROM projects WHERE workspace_id IS NOT NULL) + (SELECT count(*) FROM tasks WHERE workspace_id IS NOT NULL) + (SELECT count(*) FROM memory_entries WHERE workspace_id IS NOT NULL);"
            )
        )
    return {
        "migration": version,
        "active": active,
        "scoped_schema": scoped,
        "scoped_records": count,
    }


def fingerprints():
    return {
        table: sql(
            "SELECT md5(COALESCE(jsonb_agg(to_jsonb(t) - 'workspace_id' ORDER BY id)::text,'null')) FROM "
            + table
            + " t;"
        )
        for table in ("projects", "tasks", "memory_entries")
    }


def records(path):
    return dict(
        line.split("=", 1) for line in path.read_text().splitlines() if "=" in line
    )


def check_age(value):
    seconds = (
        datetime.now(timezone.utc) - datetime.fromisoformat(value)
    ).total_seconds()
    require(
        0 <= seconds <= 86400,
        "Evidence is older than 24 hours or has a future timestamp",
    )


def verify_sums(folder):
    for line in (folder / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        require(Path(name).name == name, "Unsafe checksum filename")
        require(
            hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest,
            "Backup checksum mismatch",
        )


def check_proofs():
    verify_sums(DB_BACKUP)
    verify_sums(FILES_BACKUP)
    restored = records(DB_BACKUP / "restore-passed.txt")
    check_age(restored["verified_at"])
    require(
        restored.get("restored_migration") == "007"
        and restored.get("task_38_done_and_merge_sha_verified") == "true"
        and restored.get("temporary_container_removed") == "true",
        "Restore proof is incomplete",
    )
    proof = records(MIGRATION_PROOF)
    check_age(proof["verified_at"])
    require(
        proof.get("candidate_image") == IMAGE
        and proof.get("migration") == "007_to_009_passed"
        and proof.get("projects_tasks_memory_preserved") == "true"
        and proof.get("automatic_classification_or_grants") == "false"
        and proof.get("temporary_containers_removed") == "true",
        "Migration rehearsal does not match this candidate",
    )
    expected_files = {str(path) for path in [*COMPOSE, ROOT / ".env"]}
    for manifest in ("source-files-before.sha256", "source-files-after.sha256"):
        seen = set()
        for line in (FILES_BACKUP / manifest).read_text().splitlines():
            digest, filename = line.split(maxsplit=1)
            require(
                filename in expected_files and filename not in seen,
                "Unexpected configuration manifest",
            )
            require(
                hashlib.sha256(Path(filename).read_bytes()).hexdigest() == digest,
                "Configuration changed after backup",
            )
            seen.add(filename)
        require(seen == expected_files, "Incomplete configuration backup")
    require(
        (FILES_BACKUP / "previous-image.txt").read_text().strip() == OLD_IMAGE,
        "Previous image backup mismatch",
    )
    q = json.loads(QUALIFICATION.read_text())
    require(
        q.get("image_id") == IMAGE
        and q.get("source_sha") == SOURCE
        and q.get("workspace_exit") == 0
        and q.get("regression_exit") == 0
        and q.get("cleanup") == "passed",
        "Candidate qualification mismatch",
    )
    for key, total in (("workspace_tests", 132), ("regression_tests", 378)):
        tests = q[key]
        require(
            tests.get("tests") == total
            and tests.get("failures") == 0
            and tests.get("errors") == 0
            and tests.get("skipped") == 1,
            "Candidate test evidence mismatch",
        )


def check_mounts(mounts):
    expected = {
        ("/app/app/artifacts", str(ROOT / "app/artifacts")),
        ("/execution/ai-team", "/opt/mywave/ai-team-execution/ai-team"),
    }
    actual = {(m["Destination"], m["Source"]) for m in mounts if m["Type"] == "bind"}
    require(
        actual == expected and len(mounts) == len(expected),
        "Unexpected application mounts",
    )


def check_idle(state):
    require(
        state["migration"] == "007"
        and not state["scoped_schema"]
        and state["scoped_records"] == 0,
        "Database differs from the reviewed 007 baseline",
    )
    require(state["active"] == 0, "An active mission or persisted run blocks release")


def check_pollers(current):
    token = environment(current).get("TELEGRAM_BOT_TOKEN")
    require(bool(token), "Production Telegram configuration is missing")
    ids = command(["docker", "ps", "-q"]).decode().split()
    matches = []
    for container in json.loads(command(["docker", "inspect", *ids])):
        env = environment(container)
        if any(
            env.get(key) == token
            for key in ("TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TG_BOT_TOKEN")
        ):
            matches.append(container["Name"])
    require(
        matches == ["/" + APP], "Another running container has the same Telegram token"
    )


def new_profile(current):
    loaded = json.loads(
        command(
            [
                "docker",
                "exec",
                "-i",
                APP,
                "python",
                "-c",
                "import json,sys,yaml; print(json.dumps(yaml.safe_load(sys.stdin)))",
            ],
            data=COMPOSE[2].read_bytes(),
        )
    )
    app = loaded["services"]["app"]
    app["image"] = IMAGE
    env = environment(inspect(IMAGE))
    require(
        env.get("APP_COMMIT_SHA") == SOURCE
        and env.get("APP_BUILD_TIMESTAMP") == "2026-10-19T19:43:52Z",
        "Candidate image identity differs",
    )
    app.setdefault("environment", {}).update(
        {
            key: env[key]
            for key in ("APP_VERSION", "APP_COMMIT_SHA", "APP_BUILD_TIMESTAMP")
        }
    )
    app["environment"].update(
        {
            "APP_ENVIRONMENT": "production",
            "WORKSPACE_ACCESS_ENABLED": "false",
            "WORKSPACE_PRINCIPAL_BINDINGS_JSON": "[]",
            "WORKSPACE_OWNER_PRINCIPAL_ID": "",
        }
    )
    return json.dumps(loaded, indent=2).encode() + b"\n"


def prepare():
    require(os.geteuid() == 0, "Run this helper as root on the intended server")
    require(shutil.disk_usage(RUNTIME).free >= 1024**3, "Less than 1 GiB free")
    current = inspect(APP)
    require(
        current["Image"] == OLD_IMAGE
        and current["State"].get("Health", {}).get("Status") == "healthy",
        "Production image or readiness changed",
    )
    require(
        current["Config"]["Labels"]
        .get("com.docker.compose.project.config_files", "")
        .split(",")
        == [str(p) for p in COMPOSE],
        "Actual Compose profile changed",
    )
    check_mounts(current["Mounts"])
    for path, digest in zip(COMPOSE, HASHES):
        require(
            not path.is_symlink()
            and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            "Compose profile changed since review",
        )
    check_proofs()
    release = api("/system/release")
    require(
        release.get("commit_sha") == OLD_SOURCE
        and release.get("migration_version") == "007",
        "Running release changed",
    )
    require(api("/system/health").get("status") == "ok", "Full system health is not OK")
    state = db_state()
    check_idle(state)
    tasks = api("/tasks")
    require(isinstance(tasks, list), "Cannot enumerate runtime missions")
    for task in tasks:
        runner = api("/tasks/" + str(task["id"]) + "/runtime").get("runner", {})
        require(
            runner.get("is_active") is False,
            "Active or unknown in-process mission blocks release",
        )
    check_pollers(current)
    configured = json.loads(compose("config", "--format", "json"))["services"]["app"]
    actual_env = environment(current)
    require(
        all(
            str(v) == actual_env.get(k)
            for k, v in configured.get("environment", {}).items()
        ),
        "Compose environment differs from running application",
    )
    return new_profile(current)


def atomic_write(path, content):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def wait_ready(image, source, migration):
    for _ in range(60):
        current = inspect(APP)
        require(current["Image"] == image, "Unexpected running image")
        if current["State"].get("Health", {}).get("Status") == "healthy":
            release = api("/system/release")
            require(
                release.get("commit_sha") == source
                and release.get("migration_version") == migration,
                "Unexpected release identity or migration",
            )
            require(
                api("/system/health").get("status") == "ok", "Full system health failed"
            )
            if image == IMAGE:
                env = environment(current)
                require(
                    env.get("WORKSPACE_ACCESS_ENABLED") == "false"
                    and env.get("WORKSPACE_PRINCIPAL_BINDINGS_JSON") == "[]"
                    and not env.get("WORKSPACE_OWNER_PRINCIPAL_ID"),
                    "Workspace intake is not disabled",
                )
                require(
                    db_state()["scoped_records"] == 0,
                    "Unexpected scoped data; legacy rollback forbidden",
                )
            return release
        time.sleep(2)
    raise RuntimeError("Application readiness timed out")


def recover(original):
    """Old image cannot run alembic when 009 is already installed."""
    compose("stop", "-t", "30", "app")
    state = db_state()
    if state["migration"] != "007" or state["scoped_schema"] or state["scoped_records"]:
        raise RuntimeError(
            "MAINTENANCE REQUIRED: app stopped; schema changed. Retain guards and repair forward; old image was NOT restarted"
        )
    atomic_write(COMPOSE[2], original)
    compose(
        "up",
        "-d",
        "--no-build",
        "--no-deps",
        "--pull",
        "never",
        "--force-recreate",
        "app",
    )
    wait_ready(OLD_IMAGE, OLD_SOURCE, "007")
    return "Previous 007 application restored and verified"


def execute(payload):
    folder = (
        RUNTIME
        / "backups"
        / (
            "workspace-cutover-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
    )
    folder.mkdir(mode=0o700)
    original = COMPOSE[2].read_bytes()
    (folder / "candidate.previous.yml").write_bytes(original)
    stopped = False
    try:
        stopped = True
        compose("stop", "-t", "30", "app")
        require(inspect(APP)["State"]["Status"] == "exited", "Old app did not stop")
        check_idle(db_state())
        before = fingerprints()
        with tarfile.open(folder / "frozen-artifacts.tar.gz", "x:gz") as archive:
            archive.add(ROOT / "app/artifacts", arcname="artifacts")
        atomic_write(COMPOSE[2], payload)
        compose("config", "--quiet")
        compose(
            "up",
            "-d",
            "--no-build",
            "--no-deps",
            "--pull",
            "never",
            "--force-recreate",
            "app",
        )
        release = wait_ready(IMAGE, SOURCE, "009")
        require(
            fingerprints() == before,
            "Legacy task/project/memory content changed during cutover",
        )
        require(
            api("/tasks/38").get("status") == "DONE"
            and api("/tasks/39").get("status") == "WAIT_OWNER",
            "Acceptance mission states changed",
        )
        check_pollers(inspect(APP))
        result = {
            "result": "WORKSPACE_RUNTIME_RELEASE_PASSED",
            "image_id": IMAGE,
            "release": release,
            "workspace_api_enabled": False,
            "legacy_data_preserved": True,
            "configuration_backup": str(FILES_BACKUP),
            "database_backup": str(DB_BACKUP),
            "cutover_evidence": str(folder),
        }
        (folder / "outcome.json").write_text(json.dumps(result, indent=2))
        return result
    except Exception as error:
        if stopped:
            try:
                outcome = recover(original)
            except Exception as rollback_error:
                (folder / "failure.json").write_text(
                    json.dumps(
                        {
                            "result": "maintenance_required",
                            "production_success": False,
                            "reason": str(rollback_error),
                        },
                        indent=2,
                    )
                )
                raise RuntimeError(str(rollback_error)) from error
            raise RuntimeError("Release failed. " + outcome) from error
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner-approved-sha")
    args = parser.parse_args()
    if args.execute and args.owner_approved_sha != SOURCE:
        parser.error(
            "--execute requires --owner-approved-sha with the exact reviewed source SHA"
        )
    os.umask(0o077)
    import fcntl

    with (RUNTIME / "owner-runtime-release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if inspect(APP)["Image"] == IMAGE:
            release = wait_ready(IMAGE, SOURCE, "009")
            print(
                json.dumps(
                    {"already_running": True, "release": release, "app_changed": False},
                    indent=2,
                )
            )
            return
        payload = prepare()
        if not args.execute:
            print(
                json.dumps(
                    {
                        "preflight": "passed",
                        "source_sha": SOURCE,
                        "image_id": IMAGE,
                        "target_migration": "009",
                        "backup_restore": "passed",
                        "migration_rehearsal": "passed",
                        "active_missions": 0,
                        "workspace_api_enabled": False,
                        "app_changed": False,
                    },
                    indent=2,
                )
            )
            return
        print(json.dumps(execute(payload), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "ERROR:",
            str(error) if isinstance(error, RuntimeError) else type(error).__name__,
        )
        raise SystemExit(1)
