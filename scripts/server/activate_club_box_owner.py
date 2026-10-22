"""Pinned app-only credential activation. Default is preview; secrets stay server-side."""

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import secrets
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path("/opt/mywave/ai-team-runtime")
PRIVATE = RUNTIME / "private/club-box"
KEY_ENV = "WORKSPACE_KEY_CLUB_BOX_OWNER"
KEY_FILE = PRIVATE / "owner.env"
IMAGE = "sha256:ddb4d20a8dc980f81abb4033f0eba75eb24073250583d2d94313e78cdd77d3f1"
SOURCE = "b2a11824342f7b7921bcb3d84dcdc8913fa8e86b"
PROFILE_HASH = "26beeda5156a59fa00f98e6b7524517e7cb745d055aaa13a9294638cb01a0478"
OPS_PATH = (
    RUNTIME
    / "workspace-release-5dedabba4d17/scripts/server/release_workspace_runtime_20261021.py"
)
OPS_HASH = "2eecbc646303badb2e611a3630276c2fec14ab7c8ae0461630d5789efdc41462"
PLAN = {
    "image_id": IMAGE,
    "source_sha": SOURCE,
    "migration": "009",
    "workspace_id": 1,
    "project_id": 2,
    "principal_id": "owner:yaroslav",
    "key_env": KEY_ENV,
    "secret_folder": "/opt/mywave/ai-team-runtime/private/club-box",
    "enable_scoped_api": True,
    "bind_shared_owner_key": False,
    "restart_service": "app",
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def plan_hash():
    return hashlib.sha256(
        json.dumps(PLAN, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_ops():
    require(
        hashlib.sha256(OPS_PATH.read_bytes()).hexdigest() == OPS_HASH,
        "Pinned operations dependency changed",
    )
    spec = importlib.util.spec_from_file_location("qualified_ops", OPS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protected(path, directory=False):
    info = path.lstat()
    require(
        not path.is_symlink()
        and info.st_uid == 0
        and not (stat.S_IMODE(info.st_mode) & 0o077),
        "Private path ownership or permissions are unsafe",
    )
    require(
        path.is_dir() if directory else path.is_file(), "Unexpected private path type"
    )


def prepare_secret():
    # Parent is an existing root-owned runtime directory, not a repository.
    info = RUNTIME.lstat()
    require(
        not RUNTIME.is_symlink()
        and info.st_uid == 0
        and not stat.S_IMODE(info.st_mode) & 0o022,
        "Unsafe runtime parent",
    )
    for path in (PRIVATE.parent, PRIVATE):
        if not path.exists() and not path.is_symlink():
            path.mkdir(mode=0o700)
        protected(path, directory=True)
    metadata = PRIVATE / "credential.json"
    if KEY_FILE.exists() or KEY_FILE.is_symlink() or metadata.exists():
        protected(KEY_FILE)
        protected(metadata)
        require(
            json.loads(metadata.read_text())
            == {
                "principal_id": PLAN["principal_id"],
                "key_env": KEY_ENV,
                "workspace_id": 1,
                "project_id": 2,
            },
            "Existing credential belongs to another plan",
        )
        read_secret()
        return False
    value = secrets.token_urlsafe(48)
    with KEY_FILE.open("x") as stream:
        stream.write(KEY_ENV + "=" + value + "\n")
    KEY_FILE.chmod(0o600)
    with metadata.open("x") as stream:
        json.dump(
            {
                "principal_id": PLAN["principal_id"],
                "key_env": KEY_ENV,
                "workspace_id": 1,
                "project_id": 2,
            },
            stream,
        )
    metadata.chmod(0o600)
    return True


def read_secret():
    protected(PRIVATE.parent, directory=True)
    protected(PRIVATE, directory=True)
    protected(KEY_FILE)
    require(KEY_FILE.stat().st_size < 256, "Unexpected secret file size")
    line = KEY_FILE.read_text().strip()
    match = re.fullmatch(re.escape(KEY_ENV) + r"=([A-Za-z0-9_-]{64})", line)
    require(match is not None, "Unexpected secret format")
    return match.group(1)


def render(profile):
    result = copy.deepcopy(profile)
    app = result["services"]["app"]
    environment = app.setdefault("environment", {})
    require(
        KEY_ENV not in environment, "Credential shadowed by inline Compose environment"
    )
    files = app.get("env_file", [])
    require(
        isinstance(files, list) and all(isinstance(p, str) for p in files),
        "Unexpected env_file structure",
    )
    if str(KEY_FILE) not in files:
        files.append(str(KEY_FILE))
    app["env_file"] = files
    environment.update(
        {
            "WORKSPACE_ACCESS_ENABLED": "true",
            "WORKSPACE_OWNER_PRINCIPAL_ID": "",
            "WORKSPACE_PRINCIPAL_BINDINGS_JSON": json.dumps(
                [{"principal_id": PLAN["principal_id"], "key_env": KEY_ENV}],
                separators=(",", ":"),
            ),
        }
    )
    return result


def probe(ops, mode="dedicated", suffix="tasks", workspace=1, project=2):
    # Credential is read inside the app process, never embedded in command arguments.
    code = (
        """import json,os,secrets,urllib.request,urllib.error
mode=__MODE__
headers={}
if mode!='none': headers['X-API-Key']=os.environ[__KEY__] if mode=='dedicated' else os.environ['OWNER_API_KEY'] if mode=='shared' else secrets.token_urlsafe(24)
r=urllib.request.Request(__URL__,headers=headers)
try:
 with urllib.request.urlopen(r,timeout=20) as response:
  result={'status':response.status}
  if response.headers.get('Content-Type','').startswith('application/json'):
   body=json.load(response);result['is_list']=isinstance(body,list);result['count']=len(body) if isinstance(body,list) else None
except urllib.error.HTTPError as error: result={'status':error.code}
print(json.dumps(result))
""".replace(
            "__MODE__", repr(mode)
        )
        .replace("__KEY__", repr(KEY_ENV))
        .replace(
            "__URL__",
            repr(
                f"http://127.0.0.1:8080/api/workspaces/{workspace}/projects/{project}/{suffix}"
            ),
        )
    )
    return json.loads(
        ops.command(["docker", "exec", ops.APP, "python", "-c", code], timeout=35)
    )


def preflight(ops):
    require(os.geteuid() == 0, "Run as root on the intended server")
    current = ops.inspect(ops.APP)
    require(
        current["Image"] == IMAGE
        and current["State"].get("Health", {}).get("Status") == "healthy",
        "App identity or health changed",
    )
    require(
        current["Config"]["Labels"]
        .get("com.docker.compose.project.config_files", "")
        .split(",")
        == [str(p) for p in ops.COMPOSE],
        "Compose profile changed",
    )
    require(
        hashlib.sha256(ops.COMPOSE[2].read_bytes()).hexdigest() == PROFILE_HASH,
        "Candidate configuration changed",
    )
    ops.check_mounts(current["Mounts"])
    env = ops.environment(current)
    require(
        env.get("WORKSPACE_ACCESS_ENABLED") == "false"
        and not env.get("WORKSPACE_OWNER_PRINCIPAL_ID")
        and env.get("WORKSPACE_PRINCIPAL_BINDINGS_JSON") == "[]"
        and KEY_ENV not in env,
        "Existing scoped authentication needs review",
    )
    configured = json.loads(ops.compose("config", "--format", "json"))["services"][
        "app"
    ]["environment"]
    require(
        all(str(v) == env.get(k) for k, v in configured.items()),
        "Compose environment drift",
    )
    state = ops.db_state()
    require(
        state["migration"] == "009"
        and state["active"] == 0
        and state["scoped_records"] == 4,
        "Database is not the reviewed idle owner bootstrap",
    )
    require(
        ops.sql(
            "SELECT count(*) FROM workspaces w JOIN projects p ON p.workspace_id=w.id JOIN workspace_memberships m ON m.workspace_id=w.id JOIN project_access_grants g ON g.project_id=p.id WHERE w.id=1 AND p.id=2 AND w.slug='mywave' AND p.slug='mywave-club-box' AND m.principal_id='owner:yaroslav' AND g.principal_id=m.principal_id AND m.role='owner' AND g.role='writer' AND m.revoked_at IS NULL AND g.revoked_at IS NULL AND m.expires_at IS NULL AND g.expires_at IS NULL"
        )
        == "1",
        "Owner grant differs",
    )
    require(ops.api("/system/health").get("status") == "ok", "Full health failed")
    ops.check_pollers(current)
    backup_root = RUNTIME / "owner-bootstrap-20261022-v1"
    proof = json.loads((backup_root / "production-verification.json").read_text())
    backup = backup_root / "post-bootstrap-009.dump"
    age = time.time() - backup.stat().st_mtime
    require(
        0 <= age <= 86400
        and proof.get("post_bootstrap_restore") == "passed"
        and hashlib.sha256(backup.read_bytes()).hexdigest()
        == proof.get("post_bootstrap_backup_sha256"),
        "Fresh restored post-bootstrap backup required",
    )
    return current


def wait_ready(ops, enabled):
    for _ in range(60):
        current = ops.inspect(ops.APP)
        require(current["Image"] == IMAGE, "App image changed during activation")
        if current["State"].get("Health", {}).get("Status") == "healthy":
            health = ops.api("/system/health")
            require(
                health["status"] == "ok"
                and health["release"]["commit_sha"] == SOURCE
                and health["release"]["migration_version"] == "009",
                "Release health or identity failed",
            )
            env = ops.environment(current)
            require(
                env.get("WORKSPACE_ACCESS_ENABLED") == str(enabled).lower(),
                "Unexpected feature setting",
            )
            require(
                not env.get("WORKSPACE_OWNER_PRINCIPAL_ID"),
                "Shared owner credential must not be bound",
            )
            return current
        time.sleep(2)
    raise RuntimeError("Application readiness timed out")


def verify_access(ops):
    results = {
        mode: probe(ops, mode) for mode in ("dedicated", "none", "wrong", "shared")
    }
    require(
        results["dedicated"].get("status") == 200
        and results["dedicated"].get("is_list") is True,
        "Dedicated credential failed",
    )
    require(
        all(results[mode].get("status") == 403 for mode in ("none", "wrong", "shared")),
        "Unexpected unauthorized access",
    )
    require(
        probe(ops, project=1)["status"] == 403
        and probe(ops, workspace=2)["status"] == 403,
        "Cross-scope access allowed",
    )
    require(probe(ops, suffix="overview")["status"] == 200, "Scoped overview failed")
    require(
        ops.api("/tasks/38")["status"] == "DONE"
        and ops.api("/tasks/39")["status"] == "WAIT_OWNER",
        "Legacy mission states changed",
    )
    for name in (
        ops.command(["docker", "ps", "--format", "{{.Names}}"]).decode().split()
    ):
        if name == ops.APP:
            continue
        env = ops.environment(ops.inspect(name))
        require(
            KEY_ENV not in env and read_secret() not in env.values(),
            "Owner credential leaked to another service",
        )
    ops.check_pollers(ops.inspect(ops.APP))
    return results


def execute(ops):
    before = ops.environment(ops.inspect(ops.APP))
    prepare_secret()
    secret = read_secret()
    require(secret != before.get("OWNER_API_KEY"), "Separate credential required")
    client_bytes = Path(__file__).with_name("club_box_owner_status.py").read_bytes()
    (PRIVATE / "status.py").write_bytes(client_bytes)
    (PRIVATE / "status.py").chmod(0o600)
    (PRIVATE / "README.txt").write_text(
        "Club Box owner credential. Root-only. Do not copy into Git or shared .env.\nCheck access: python3 "
        + str(PRIVATE / "status.py")
        + "\nThis folder is not the portable Club Box distribution.\n"
    )
    original = ops.COMPOSE[2].read_bytes()
    payload = json.dumps(render(json.loads(original)), indent=2).encode() + b"\n"
    folder = PRIVATE / (
        "activation-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    folder.mkdir(mode=0o700)
    (folder / "candidate.previous.json").write_bytes(original)
    (folder / "owner.env.backup").write_bytes(KEY_FILE.read_bytes())
    (folder / "credential.json").write_bytes((PRIVATE / "credential.json").read_bytes())
    try:
        ops.atomic_write(ops.COMPOSE[2], payload)
        configured = json.loads(ops.compose("config", "--format", "json"))["services"][
            "app"
        ]["environment"]
        allowed = {
            KEY_ENV,
            "WORKSPACE_ACCESS_ENABLED",
            "WORKSPACE_PRINCIPAL_BINDINGS_JSON",
            "WORKSPACE_OWNER_PRINCIPAL_ID",
        }
        require(
            configured.get(KEY_ENV) == secret
            and all(
                str(v) == before.get(k)
                for k, v in configured.items()
                if k not in allowed
            ),
            "Unexpected environment changes",
        )
        ops.compose(
            "up",
            "-d",
            "--no-build",
            "--no-deps",
            "--pull",
            "never",
            "--force-recreate",
            "app",
        )
        wait_ready(ops, True)
        results = verify_access(ops)
    except Exception as error:
        try:
            ops.atomic_write(ops.COMPOSE[2], original)
            ops.compose(
                "up",
                "-d",
                "--no-build",
                "--no-deps",
                "--pull",
                "never",
                "--force-recreate",
                "app",
            )
            wait_ready(ops, False)
        except Exception as recovery:
            raise RuntimeError(
                "Activation and configuration recovery failed; inspect current app"
            ) from recovery
        raise RuntimeError(
            "Activation failed; same image restored with scoped API disabled"
        ) from error
    result = {
        "result": "OWNER_API_ACTIVATED",
        "image_id": IMAGE,
        "workspace_id": 1,
        "project_id": 2,
        "secret_folder": str(PRIVATE),
        "secret_value_printed": False,
        "shared_owner_key_bound": False,
        "auth_statuses": {k: v["status"] for k, v in results.items()},
    }
    (folder / "outcome.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner-approved-plan")
    args = parser.parse_args()
    require(not (args.prepare and args.execute), "Choose prepare or execute")
    if args.execute:
        require(
            args.owner_approved_plan == plan_hash(),
            "Exact owner-approved activation plan required",
        )
    os.umask(0o077)
    import fcntl

    ops = load_ops()
    with (RUNTIME / "owner-runtime-release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = ops.inspect(ops.APP)
        env = ops.environment(current)
        if env.get("WORKSPACE_ACCESS_ENABLED") == "true":
            require(
                current["Image"] == IMAGE and env.get(KEY_ENV) == read_secret(),
                "Unexpected active credential or image",
            )
            require(
                json.loads(env.get("WORKSPACE_PRINCIPAL_BINDINGS_JSON", "[]"))
                == [{"principal_id": PLAN["principal_id"], "key_env": KEY_ENV}],
                "Unexpected active principal bindings",
            )
            wait_ready(ops, True)
            verify_access(ops)
            print(
                json.dumps(
                    {
                        "already_active": True,
                        "secret_folder": str(PRIVATE),
                        "app_changed": False,
                    },
                    indent=2,
                )
            )
            return
        preflight(ops)
        if args.execute:
            result = execute(ops)
        elif args.prepare:
            created = prepare_secret()
            result = {
                "mode": "prepare",
                "credential_created": created,
                "secret_folder": str(PRIVATE),
                "app_changed": False,
                "secret_value_printed": False,
            }
        else:
            result = {
                "mode": "preview",
                "plan": PLAN,
                "plan_sha256": plan_hash(),
                "app_changed": False,
            }
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
