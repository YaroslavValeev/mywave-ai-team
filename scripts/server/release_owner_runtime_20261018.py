"""Pinned, owner-operated app-only rollout. Default is a read-only preflight."""

import argparse
import copy
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

SOURCE_SHA = "20476d9fd5a8df89dd9ae33c1c61957569c39307"
IMAGE_ID = "sha256:f85bdfc8aa43952d074521e295c312da97bda74ebc77435d6a2feece34415dc1"
BASE_ID = "sha256:89d5bf10e96ae1d13cf2c433a6d5543db84eec9e40ea4eb957b6717809d5cf17"
BASE_SHA = "5922c136887404258c3733261bcb1def1ec235bc"
APP = "ai-team-app-1"
ROOT = Path("/opt/mywave/ai-team")
RUNTIME = Path("/opt/mywave/ai-team-runtime")
QA = RUNTIME / "qa-20261018-20476d9"
COMPOSE = [
    ROOT / "docker-compose.yml",
    ROOT / "docker-compose.server-full.yml",
    RUNTIME / "candidate.yml",
]
BACKUP = RUNTIME / "backups/recovery-20261018T075555734481Z.dump"
RESTORE = RUNTIME / "backups/restore-20261018T075555734481Z.json"
PROFILE_HASHES = [
    "7d8a18719bf53fb0e3a094f14426dc308dc0b4672a4f5730de5d999e37bc3219",
    "c19db2e3f822101559a24343a48ad17ede2f3070e8c5a3bf4f17b5113610885b",
    "e5f17db24520b2e7f10b385772d07b446dc11060a9d60507e0d7fc594676a0b8",
]


def verify_source_mounts(mounts):
    for mount in mounts:
        target = mount["Destination"].rstrip("/")
        if target == "/app/app/artifacts" or target.startswith("/app/app/artifacts/"):
            continue
        if target == "/app" or any(
            target == root or target.startswith(root + "/")
            for root in ("/app/app", "/app/packages", "/app/services", "/app/src")
        ):
            raise RuntimeError(
                "A source-code mount overrides image provenance; rollout blocked"
            )


def command(args, *, data=None, timeout=120):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("Command failed; no configuration values were printed")
    return result.stdout


def inspect(reference):
    return json.loads(command(["docker", "inspect", reference]))[0]


def compose(*args):
    flags = [part for path in COMPOSE for part in ("-f", str(path))]
    return command(
        ["docker", "compose", "--project-directory", str(ROOT), *flags, *args]
    )


def api(path):
    code = (
        "import json,os,urllib.request; "
        "r=urllib.request.Request('http://127.0.0.1:8080/api'+"
        + repr(path)
        + ",headers={'X-API-Key':os.environ['OWNER_API_KEY']}); "
        "print(json.dumps(json.load(urllib.request.urlopen(r,timeout=20))))"
    )
    return json.loads(
        command(["docker", "exec", APP, "python", "-c", code], timeout=35)
    )


def atomic_write(path, content):
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_release(payloads, up, verify_new, verify_old):
    """Restore both configuration and the previous app if any rollout step fails."""
    originals = {path: path.read_bytes() for path in payloads}
    try:
        for path, content in payloads.items():
            atomic_write(path, content)
        up()
        return verify_new()
    except Exception as error:
        try:
            for path, content in originals.items():
                atomic_write(path, content)
            up()
            verify_old()
        except Exception as rollback_error:
            raise RuntimeError(
                "Rollout failed AND rollback verification failed; inspect the app"
            ) from rollback_error
        raise RuntimeError(
            "Rollout failed; previous app and configuration restored and verified"
        ) from error


def check_proof(proof):
    tests = proof.get("tests", {})
    if (
        proof.get("source_sha") != SOURCE_SHA
        or proof.get("image_id") != IMAGE_ID
        or proof.get("base_image_id") != BASE_ID
        or proof.get("pytest_exit") != 0
        or int(tests.get("tests", 0)) != 378
        or int(tests.get("errors", -1)) != 0
        or int(tests.get("failures", -1)) != 0
        or int(tests.get("skipped", -1)) != 1
    ):
        raise RuntimeError("Candidate qualification does not match this release")


def wait_release(image_id, sha, full):
    for _ in range(60):
        current = inspect(APP)
        if current["Image"] != image_id:
            raise RuntimeError("Unexpected running app image")
        if current["State"].get("Health", {}).get("Status") == "healthy":
            release = api("/system/release")
            if (
                release.get("commit_sha") != sha
                or release.get("migration_version") != "007"
            ):
                raise RuntimeError("Unexpected running release or migration")
            if full:
                health = api("/system/health")
                if (
                    health.get("status") != "ok"
                    or health.get("checks", {}).get("molt", {}).get("status") != "ok"
                ):
                    raise RuntimeError("Full system/Molt readiness did not pass")
                if (
                    api("/tasks/38").get("status") != "DONE"
                    or api("/tasks/39").get("status") != "WAIT_OWNER"
                ):
                    raise RuntimeError(
                        "Mission state changed during the maintenance window"
                    )
                metrics = api("/tasks/39/outcome-metrics")
                if (
                    metrics.get("business_outcome_verified") is not False
                    or metrics.get("verified_owner_hours_saved") is not None
                ):
                    raise RuntimeError("Missing KPI evidence is presented as verified")
                return {
                    "release": release,
                    "health_status": health["status"],
                    "molt": "ok",
                    "task_38": "DONE",
                    "task_39": "WAIT_OWNER",
                    "unmeasured_kpi_verified": False,
                }
            return {"release": release, "rollback_image_verified": image_id}
        time.sleep(2)
    raise RuntimeError("App did not become healthy in the allowed interval")


def prepare():
    proof = json.loads((QA / "qualification.json").read_text())
    check_proof(proof)
    smoke = json.loads((QA / "crewai-smoke.json").read_text())
    if (
        smoke.get("source_sha") != SOURCE_SHA
        or smoke.get("real_crewai_local_smoke_passed") is not True
    ):
        raise RuntimeError("Isolated real CrewAI qualification is missing")
    image = inspect(IMAGE_ID)
    env = dict(item.split("=", 1) for item in image["Config"]["Env"] if "=" in item)
    if (
        env.get("APP_COMMIT_SHA") != SOURCE_SHA
        or env.get("APP_BUILD_TIMESTAMP") != proof["build_timestamp"]
    ):
        raise RuntimeError("Image metadata differs from qualification")
    current = inspect(APP)
    if current["Image"] != BASE_ID:
        raise RuntimeError("Current app changed; this release must be reviewed again")
    verify_source_mounts(current.get("Mounts", []))
    expected_files = [str(path) for path in COMPOSE]
    labels = current["Config"].get("Labels", {})
    if (
        labels.get("com.docker.compose.project.config_files", "").split(",")
        != expected_files
    ):
        raise RuntimeError("Running app uses a different Compose file set")
    for path, expected in zip(COMPOSE, PROFILE_HASHES):
        if (
            path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise RuntimeError(
                "Compose configuration changed since review; rollout blocked"
            )
    restore = json.loads(RESTORE.read_text())
    if (
        restore.get("isolated_restore") != "passed"
        or restore.get("cleanup") != "passed"
        or restore.get("backup") != str(BACKUP)
        or hashlib.sha256(BACKUP.read_bytes()).hexdigest() != restore.get("sha256")
    ):
        raise RuntimeError("Backup/restore evidence is missing or changed")
    age = datetime.now(timezone.utc) - datetime.fromisoformat(restore["captured_at"])
    if not 0 <= age.total_seconds() <= 86400:
        raise RuntimeError("A fresh backup and restore drill is required")
    if api("/system/release").get("commit_sha") != BASE_SHA:
        raise RuntimeError("Current source identity changed")
    tasks = api("/tasks")
    if not isinstance(tasks, list):
        raise RuntimeError("Could not enumerate missions")
    for task in tasks:
        if task.get("status") in {"IN_PIPELINE", "EXECUTING"} or api(
            f"/tasks/{task['id']}/runtime"
        ).get("runner", {}).get("is_active"):
            raise RuntimeError(
                "Active mission found; wait for an idle maintenance window"
            )
    configured = json.loads(compose("config", "--format", "json"))["services"]["app"]
    running_env = dict(
        item.split("=", 1) for item in current["Config"]["Env"] if "=" in item
    )
    if any(
        str(value) != running_env.get(key)
        for key, value in configured.get("environment", {}).items()
    ):
        raise RuntimeError(
            "Compose environment drift detected; do not apply unrelated settings"
        )

    def read_yaml(path):
        return json.loads(
            command(
                [
                    "docker",
                    "exec",
                    "-i",
                    APP,
                    "python",
                    "-c",
                    "import sys,json,yaml; print(json.dumps(yaml.safe_load(sys.stdin)))",
                ],
                data=path.read_bytes(),
            )
        )

    candidate = copy.deepcopy(read_yaml(COMPOSE[2]))
    candidate["services"]["app"].setdefault("environment", {}).update(
        {
            key: env[key]
            for key in ("APP_VERSION", "APP_COMMIT_SHA", "APP_BUILD_TIMESTAMP")
        }
    )
    candidate["services"]["app"]["environment"]["APP_ENVIRONMENT"] = "production"
    candidate["services"]["app"]["image"] = IMAGE_ID
    payloads = {COMPOSE[2]: json.dumps(candidate, indent=2).encode()}
    return payloads


def backup_configs():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = RUNTIME / "backups" / ("app-cutover-" + stamp)
    folder.mkdir(mode=0o700)
    for path in COMPOSE[2:]:
        shutil.copy2(path, folder / path.name)
    with tarfile.open(folder / "configuration.tar.gz", "x:gz") as archive:
        for index, path in enumerate([*COMPOSE, ROOT / ".env"]):
            archive.add(path, arcname=str(index) + "-" + path.name, recursive=False)
    with (folder / "artifacts.tar").open("xb") as stream:
        result = subprocess.run(
            ["docker", "exec", APP, "tar", "-C", "/app/app", "-cf", "-", "artifacts"],
            stdout=stream,
            stderr=subprocess.PIPE,
            timeout=120,
        )
    if result.returncode:
        raise RuntimeError("Artifact backup failed; app was not changed")
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner-approved-sha")
    args = parser.parse_args()
    if args.execute and args.owner_approved_sha != SOURCE_SHA:
        parser.error(
            "Execution requires --owner-approved-sha with the exact reviewed source SHA"
        )
    os.umask(0o077)
    import fcntl

    with (RUNTIME / "owner-runtime-release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if inspect(APP)["Image"] == IMAGE_ID:
            result = wait_release(IMAGE_ID, SOURCE_SHA, True)
            result["already_running"] = True
            print(json.dumps(result, indent=2))
            return
        payloads = prepare()
        if not args.execute:
            print(
                json.dumps(
                    {
                        "preflight": "passed",
                        "source_sha": SOURCE_SHA,
                        "candidate_image": IMAGE_ID,
                        "app_changed": False,
                        "backup_restore": "passed",
                    },
                    indent=2,
                )
            )
            return
        if shutil.disk_usage(RUNTIME).free < 1024**3:
            raise RuntimeError("Less than 1 GiB free; rollout cancelled")
        backup = backup_configs()

        def up():
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

        result = apply_release(
            payloads,
            up,
            lambda: wait_release(IMAGE_ID, SOURCE_SHA, True),
            lambda: wait_release(BASE_ID, BASE_SHA, False),
        )
        result.update(
            {
                "source_sha": SOURCE_SHA,
                "image_id": IMAGE_ID,
                "configuration_backup": str(backup),
            }
        )
        (backup / "outcome.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "ERROR:",
            str(error) if isinstance(error, RuntimeError) else type(error).__name__,
        )
        raise SystemExit(1)
