"""Pinned console release. Preview by default; prepare and Owner Gate are separate."""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import http.cookiejar
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

RUNTIME = Path("/opt/mywave/ai-team-runtime")
SOURCE = "898386aa1c1b766a3db088235163cf128dfa17ef"
IMAGE = "sha256:d5e33200cb8e5f66ea8ad93ed9d415d35f5c7f269dc08d6a3825bb0426dbe6e3"
VERSION = "2026-10-23-898386aa1c1b"
ACTIVATION = (
    RUNTIME / "owner-auth-20261022-v3/scripts/server/activate_club_box_owner.py"
)
ACTIVATION_HASH = "eef637b59036b4cb1bd0b27b3bd888977b70265507ff92b5b7781165f555e030"
QUALIFICATION = RUNTIME / "project-console-qa-898386aa1c1b-mrgcnwe1/qualification.json"
TABLES = (
    "projects",
    "tasks",
    "memory_entries",
    "workspaces",
    "workspace_memberships",
    "project_access_grants",
)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def plan_hash(plan):
    return digest(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode())


def load_ops():
    require(
        digest(ACTIVATION.read_bytes()) == ACTIVATION_HASH,
        "Activation dependency changed",
    )
    spec = importlib.util.spec_from_file_location("qualified_activation", ACTIVATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module.load_ops()


def trusted_proxies(container):
    networks = container["NetworkSettings"]["Networks"]
    require(len(networks) == 1, "Review multiple network paths before release")
    gateway = next(iter(networks.values()))["Gateway"]
    require(ipaddress.ip_address(gateway).is_private, "Unexpected proxy gateway")
    return "127.0.0.1,::1," + gateway


def render(profile, trust, built_at):
    require(
        trust
        and all("/" not in p and ipaddress.ip_address(p) for p in trust.split(",")),
        "Exact proxy addresses required",
    )
    result = copy.deepcopy(profile)
    app = result["services"]["app"]
    app["image"] = IMAGE
    app.setdefault("environment", {}).update(
        APP_VERSION=VERSION,
        APP_COMMIT_SHA=SOURCE,
        APP_BUILD_TIMESTAMP=built_at,
        APP_ENVIRONMENT="production",
        FORWARDED_ALLOW_IPS=trust,
    )
    return result


def nginx_gate(ops, base_url):
    parsed = urllib.parse.urlsplit(base_url)
    require(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.netloc == parsed.hostname
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment,
        "Canonical HTTPS URL required",
    )
    config = ops.command(["nginx", "-T"]).decode()
    blocks = []
    for match in re.finditer(r"\bserver\s*\{", config):
        start = match.end()
        end = start
        depth = 1
        while depth and end < len(config):
            depth += (config[end] == "{") - (config[end] == "}")
            end += 1
        block = config[start:end]
        if any(
            parsed.hostname in names.split()
            for names in re.findall(r"server_name\s+([^;]+);", block)
        ):
            blocks.append(block)
    tls = [b for b in blocks if re.search(r"listen\s+[^;]*443[^;]*ssl", b)]
    require(tls, "TLS vhost not verified")
    require(
        all(
            re.search(r"proxy_set_header\s+X-Forwarded-Proto\s+\$scheme", b, re.I)
            for b in tls
        ),
        "Forwarded protocol missing",
    )
    upstreams = [
        p.strip() for b in tls for p in re.findall(r"proxy_pass\s+([^;]+);", b)
    ]
    require(
        upstreams
        and all(
            p.rstrip("/") in {"http://127.0.0.1:8088", "http://localhost:8088"}
            for p in upstreams
        ),
        "Review TLS upstream before using a dedicated credential",
    )
    headers = [
        v.strip().strip('"')
        for b in blocks
        for v in re.findall(r"proxy_set_header\s+X-API-Key\s+([^;]+);", b, re.I)
    ]
    require(
        all(v == "$http_x_api_key" for v in headers), "Proxy changes the dedicated key"
    )
    return base_url.rstrip("/")


def public_health(base_url, source):
    with urllib.request.urlopen(base_url + "/health", timeout=20) as response:
        health = json.load(response)
    require(
        health["status"] == "ok"
        and health["release"]["commit_sha"] == source
        and health["release"]["migration_version"] == "009",
        "Public health or TLS identity failed",
    )


def preflight(activation, ops, base_url):
    current = ops.inspect(ops.APP)
    env = ops.environment(current)
    require(
        current["Image"] == activation.IMAGE
        and current["State"].get("Health", {}).get("Status") == "healthy",
        "Base image or health changed",
    )
    require(
        current["Config"]["Labels"]
        .get("com.docker.compose.project.config_files", "")
        .split(",")
        == [str(p) for p in ops.COMPOSE],
        "Compose files changed",
    )
    ops.check_mounts(current["Mounts"])
    ops.check_pollers(current)
    require(
        env.get("WORKSPACE_ACCESS_ENABLED") == "true"
        and not env.get("WORKSPACE_OWNER_PRINCIPAL_ID")
        and env.get(activation.KEY_ENV) == activation.read_secret(),
        "Scoped credential or setting changed",
    )
    require(
        json.loads(env.get("WORKSPACE_PRINCIPAL_BINDINGS_JSON", "[]"))
        == [{"principal_id": "owner:yaroslav", "key_env": activation.KEY_ENV}],
        "Principal binding changed",
    )
    require(
        ops.db_state()["migration"] == "009" and ops.db_state()["active"] == 0,
        "Migration or active operation prevents release",
    )
    require(ops.api("/system/health")["status"] == "ok", "Full system health failed")
    activation.verify_access(ops)
    ports = current["HostConfig"]["PortBindings"].get("8080/tcp", [])
    require(
        ports == [{"HostIp": "127.0.0.1", "HostPort": "8088"}],
        "Review application exposure",
    )
    configured = json.loads(ops.compose("config", "--format", "json"))["services"][
        "app"
    ]["environment"]
    require(
        all(str(value) == env.get(key) for key, value in configured.items()),
        "Compose environment drift",
    )
    qualification = json.loads(QUALIFICATION.read_text())
    require(
        qualification.get("result") == "passed"
        and qualification.get("cleanup") == "passed"
        and qualification["source_sha"] == SOURCE
        and qualification["image_id"] == IMAGE,
        "Candidate qualification mismatch",
    )
    proxy_proof = (RUNTIME / "console-proxy-qualification.json").read_bytes()
    proxy = json.loads(proxy_proof)
    require(
        proxy.get("result") == "passed"
        and proxy.get("cleanup") == "passed"
        and proxy["image_id"] == IMAGE
        and proxy["source_sha"] == SOURCE
        and proxy["secure_cookie"] == "passed"
        and proxy["untrusted_forwarded_proto"] == "denied_400",
        "Proxy qualification missing or mismatched",
    )
    image = json.loads(ops.command(["docker", "image", "inspect", IMAGE]))[0]
    image_env = ops.environment(image)
    require(
        image_env.get("APP_COMMIT_SHA") == SOURCE
        and image_env.get("APP_BUILD_TIMESTAMP") not in (None, "unknown", ""),
        "Candidate identity mismatch",
    )
    base_url = nginx_gate(ops, base_url)
    public_health(base_url, activation.SOURCE)
    profile = ops.COMPOSE[2].read_bytes()
    plan = {
        "source_sha": SOURCE,
        "candidate_image": IMAGE,
        "previous_image": activation.IMAGE,
        "operations_sha256": digest(Path(__file__).read_bytes()),
        "proxy_qualification_sha256": digest(proxy_proof),
        "profile_sha256": digest(profile),
        "compose_sha256": [digest(p.read_bytes()) for p in ops.COMPOSE],
        "forwarded_allow_ips": trusted_proxies(current),
        "build_timestamp": image_env["APP_BUILD_TIMESTAMP"],
        "public_base_url": base_url,
        "restart_service": "app",
        "schema": "009",
        "migrate": False,
        "rotate_key": False,
    }
    return plan, profile


def fingerprints(sql):
    return {
        table: sql(
            f"SELECT md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'null')) FROM {table} t;"
        )
        for table in TABLES
    }


def prepare(activation, ops, plan, original):
    require(shutil.disk_usage(RUNTIME).free > 1024**3, "At least 1 GiB free required")
    folder = Path(tempfile.mkdtemp(prefix="console-release-", dir=RUNTIME))
    (folder / "candidate.previous.json").write_bytes(original)
    (folder / "owner.env.backup").write_bytes(activation.KEY_FILE.read_bytes())
    before = fingerprints(ops.sql)
    backup = ops.command(
        [
            "docker",
            "exec",
            ops.PG,
            "sh",
            "-ec",
            'exec pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" -d "${POSTGRES_DB:-$POSTGRES_USER}"',
        ],
        timeout=180,
    )
    require(bool(backup), "Empty backup")
    (folder / "database.dump").write_bytes(backup)
    require(
        before == fingerprints(ops.sql), "Data changed during backup; prepare again"
    )
    name = "console-restore-" + uuid.uuid4().hex
    pg_image = ops.inspect(ops.PG)["Image"]
    try:
        ops.command(
            [
                "docker",
                "run",
                "-d",
                "--pull",
                "never",
                "--name",
                name,
                "--label",
                "mywave.console-restore=" + name,
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
            try:
                ops.command(
                    [
                        "docker",
                        "exec",
                        name,
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "qa",
                        "-d",
                        "qa",
                    ]
                )
                break
            except RuntimeError:
                time.sleep(1)
        else:
            raise RuntimeError("Restore PostgreSQL unavailable")
        ops.command(
            [
                "docker",
                "exec",
                "-i",
                name,
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "-U",
                "qa",
                "-d",
                "qa",
            ],
            data=backup,
        )
        sql = (
            lambda query: ops.command(
                [
                    "docker",
                    "exec",
                    name,
                    "psql",
                    "-X",
                    "-U",
                    "qa",
                    "-d",
                    "qa",
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
        require(
            sql("SELECT version_num FROM alembic_version;") == "009"
            and fingerprints(sql) == before,
            "Restored data mismatch",
        )
    finally:
        try:
            container = ops.inspect(name)
        except RuntimeError:
            container = None
        if container:
            require(
                container["Config"]["Labels"].get("mywave.console-restore") == name,
                "Restore cleanup ownership mismatch",
            )
            ops.command(["docker", "rm", "-f", "-v", name])
    proof = {
        "plan": plan,
        "plan_sha256": plan_hash(plan),
        "database_sha256": digest(backup),
        "fingerprints": before,
        "restore": "passed",
        "cleanup": "passed",
        "prepared_at": time.time(),
    }
    (folder / "prepared.json").write_text(json.dumps(proof, indent=2))
    return folder


def wait_ready(ops, image, source):
    for _ in range(60):
        current = ops.inspect(ops.APP)
        require(current["Image"] == image, "Unexpected running image")
        if current["State"].get("Health", {}).get("Status") == "healthy":
            health = ops.api("/system/health")
            require(
                health["status"] == "ok"
                and health["release"]["commit_sha"] == source
                and health["release"]["migration_version"] == "009",
                "Release verification failed",
            )
            return
        time.sleep(2)
    raise RuntimeError("Readiness timed out")


def verify_public(activation, base_url):
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(path, method="GET", headers=None):
        req = urllib.request.Request(
            base_url + "/api/workspaces" + path, method=method, headers=headers or {}
        )
        with client.open(req, timeout=20) as response:
            return response.status, response.headers, response.read()

    status, headers, _ = request(
        "/session", "POST", {"X-API-Key": activation.read_secret()}
    )
    require(
        status == 200 and any(cookie.secure for cookie in jar),
        "Secure browser session failed",
    )
    projects = json.loads(request("/projects")[2])
    require(
        any(p["workspace_id"] == 1 and p["project_id"] == 2 for p in projects),
        "Club Box project unavailable",
    )
    require(request("/1/projects/2/tasks")[0] == 200, "Scoped browser read failed")
    request("/session", "DELETE", {"X-Workspace-Request": "1"})
    try:
        request("/projects")
    except urllib.error.HTTPError as error:
        require(error.code == 403, "Logout verification failed")
    else:
        raise RuntimeError("Session survived logout")


def cutover(ops, original, replacement, ready, verify, recover):
    def up():
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

    try:
        ops.atomic_write(ops.COMPOSE[2], replacement)
        up()
        ready()
        verify()
    except Exception:
        try:
            ops.atomic_write(ops.COMPOSE[2], original)
            up()
            recover()
        except Exception:
            raise RuntimeError("Release and recovery failed; inspect app") from None
        raise RuntimeError(
            "Release failed; previous 009 image/configuration recovered"
        ) from None


def execute(activation, ops, plan, original, prepared, approval):
    require(approval == plan_hash(plan), "Exact release Owner Gate required")
    activation.protected(prepared, directory=True)
    require(
        prepared.parent == RUNTIME and prepared.name.startswith("console-release-"),
        "Unexpected preparation directory",
    )
    activation.protected(prepared / "prepared.json")
    for name in ("database.dump", "candidate.previous.json", "owner.env.backup"):
        activation.protected(prepared / name)
    proof = json.loads((prepared / "prepared.json").read_text())
    require(
        proof["plan_sha256"] == plan_hash(plan)
        and proof["restore"] == "passed"
        and proof["cleanup"] == "passed"
        and 0 <= time.time() - proof["prepared_at"] <= 86400,
        "Fresh matching restored backup required",
    )
    require(
        digest((prepared / "database.dump").read_bytes()) == proof["database_sha256"]
        and (prepared / "candidate.previous.json").read_bytes() == original
        and (prepared / "owner.env.backup").read_bytes()
        == activation.KEY_FILE.read_bytes()
        and fingerprints(ops.sql) == proof["fingerprints"],
        "Backup, key or data changed; prepare again",
    )
    replacement = (
        json.dumps(
            render(
                json.loads(original),
                plan["forwarded_allow_ips"],
                plan["build_timestamp"],
            ),
            indent=2,
        )
        + "\n"
    ).encode()

    def verify():
        require(
            ops.environment(ops.inspect(ops.APP)).get("FORWARDED_ALLOW_IPS")
            == plan["forwarded_allow_ips"],
            "Proxy trust differs",
        )
        activation.verify_access(ops)
        public_health(plan["public_base_url"], SOURCE)
        verify_public(activation, plan["public_base_url"])

    cutover(
        ops,
        original,
        replacement,
        lambda: wait_ready(ops, IMAGE, SOURCE),
        verify,
        lambda: (
            wait_ready(ops, activation.IMAGE, activation.SOURCE),
            activation.verify_access(ops),
        ),
    )
    outcome = {
        "result": "PROJECT_CONSOLE_RELEASE_PASSED",
        "source_sha": SOURCE,
        "image_id": IMAGE,
        "plan_sha256": plan_hash(plan),
        "secure_public_session": "passed",
        "backup_restore": "passed",
        "migrations_changed": False,
    }
    (prepared / "outcome.json").write_text(json.dumps(outcome, indent=2))
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-base-url", required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--prepared")
    parser.add_argument("--owner-approved-plan")
    args = parser.parse_args()
    require(not (args.prepare and args.execute), "Choose prepare or execute")
    if args.execute:
        require(
            args.prepared
            and re.fullmatch("[0-9a-f]{64}", args.owner_approved_plan or ""),
            "Prepared evidence and explicit Owner Gate required",
        )
    require(os.geteuid() == 0, "Run as root on the intended server")
    os.umask(0o077)
    import fcntl

    activation, ops = load_ops()
    for path in (RUNTIME, *ops.COMPOSE):
        info = path.lstat()
        require(
            not path.is_symlink()
            and info.st_uid == 0
            and not stat.S_IMODE(info.st_mode) & 0o022,
            "Unsafe runtime configuration path",
        )
    with (RUNTIME / "owner-runtime-release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if ops.inspect(ops.APP)["Image"] == IMAGE:
            current = ops.inspect(ops.APP)
            require(
                ops.environment(current).get("FORWARDED_ALLOW_IPS")
                == trusted_proxies(current),
                "Active proxy trust differs",
            )
            url = nginx_gate(ops, args.public_base_url)
            wait_ready(ops, IMAGE, SOURCE)
            activation.verify_access(ops)
            public_health(url, SOURCE)
            verify_public(activation, url)
            print(json.dumps({"already_active": True, "app_changed": False}))
            return
        plan, original = preflight(activation, ops, args.public_base_url)
        if args.execute:
            result = execute(
                activation,
                ops,
                plan,
                original,
                Path(args.prepared),
                args.owner_approved_plan,
            )
        elif args.prepare:
            result = {
                "prepared_directory": str(prepare(activation, ops, plan, original)),
                "plan": plan,
                "plan_sha256": plan_hash(plan),
                "app_changed": False,
            }
        else:
            result = {
                "mode": "preview",
                "plan": plan,
                "plan_sha256": plan_hash(plan),
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
