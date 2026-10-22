"""Real app.main behind a simulated host proxy; synthetic keys, isolated network."""

import argparse
from http.cookies import SimpleCookie
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request
import uuid

path = Path(__file__).resolve().parents[1] / "server/project_console_release.py"
spec = importlib.util.spec_from_file_location("console_release", path)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "preview",
                    "candidate_image": release.IMAGE,
                    "production_changed": False,
                }
            )
        )
        return
    release.require(os.geteuid() == 0, "Run on the intended server as root")
    os.umask(0o077)
    _, ops = release.load_ops()
    before = ops.inspect(ops.APP)
    release.require(
        before["State"].get("Health", {}).get("Status") == "healthy",
        "Production must be healthy",
    )
    folder = Path(tempfile.mkdtemp(prefix="console-proxy-qa-", dir=release.RUNTIME))
    ident = uuid.uuid4().hex
    network = "console-proxy-" + ident
    app = "console-proxy-app-" + ident
    probe = "console-proxy-probe-" + ident
    report = {
        "source_sha": release.SOURCE,
        "image_id": release.IMAGE,
        "production_changed": False,
        "synthetic_credentials_only": True,
        "qa_code_sha256": release.digest(Path(__file__).read_bytes()),
    }
    label = "mywave.console-proxy=" + ident

    def run(args, timeout=120):
        return ops.command(args, timeout=timeout)

    try:
        run(["docker", "network", "create", "--internal", "--label", label, network])
        gateway = json.loads(run(["docker", "network", "inspect", network]))[0]["IPAM"][
            "Config"
        ][0]["Gateway"]
        seed = """from sqlalchemy.orm import Session
from app.storage.models import Base,Workspace,Project,WorkspaceMembership,ProjectAccessGrant
from app.storage.repositories import get_engine
import subprocess
engine=get_engine();Base.metadata.create_all(engine)
with Session(engine) as session:
 w=Workspace(slug='proxy-qa',name='QA',kind='MYWAVE',owner_id='qa');session.add(w);session.flush()
 p=Project(slug='proxy-qa',name='QA project',workspace_id=w.id);session.add(p);session.flush()
 session.add_all([WorkspaceMembership(workspace_id=w.id,principal_id='qa',role='owner'),ProjectAccessGrant(project_id=p.id,principal_id='qa',role='writer')]);session.commit()
subprocess.run(['python','-m','app.main'],check=True)
"""
        bindings = '[{"principal_id":"qa","key_env":"WORKSPACE_KEY_QA"}]'
        run(
            [
                "docker",
                "run",
                "-d",
                "--pull",
                "never",
                "--name",
                app,
                "--label",
                label,
                "--network",
                network,
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
                "DATABASE_URL=sqlite:////tmp/proxy-qa.sqlite",
                "-e",
                "OWNER_API_KEY=synthetic-proxy-qa-legacy",
                "-e",
                "WORKSPACE_ACCESS_ENABLED=true",
                "-e",
                "WORKSPACE_OWNER_PRINCIPAL_ID=",
                "-e",
                "WORKSPACE_PRINCIPAL_BINDINGS_JSON=" + bindings,
                "-e",
                "WORKSPACE_KEY_QA=synthetic-proxy-qa-project",
                "-e",
                "TELEGRAM_POLLING_ENABLED=false",
                "-e",
                "TELEGRAM_PROACTIVE_NOTIFY_ENABLED=false",
                "-e",
                "ORCHESTRATION_ENGINE=rule_based",
                "-e",
                "ARTIFACTS_DIR=/tmp/artifacts",
                "-e",
                "DASHBOARD_PORT=8080",
                "-e",
                "FORWARDED_ALLOW_IPS=127.0.0.1,::1," + gateway,
                "--entrypoint",
                "python",
                release.IMAGE,
                "-c",
                seed,
            ]
        )
        address = ops.inspect(app)["NetworkSettings"]["Networks"][network]["IPAddress"]
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def call(path, method="GET", cookie=None, forwarded=True, key=None):
            headers = {"Host": app}
            if forwarded:
                headers["X-Forwarded-Proto"] = "https"
            if cookie:
                headers["Cookie"] = cookie
            if key:
                headers["X-API-Key"] = key
            req = urllib.request.Request(
                "http://" + address + ":8080" + path, headers=headers, method=method
            )
            try:
                with client.open(req, timeout=5) as response:
                    return response.status, response.headers, response.read()
            except urllib.error.HTTPError as error:
                return error.code, error.headers, b""

        for _ in range(90):
            try:
                if call("/health")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("QA application readiness failed")
        code, headers, _ = call(
            "/api/workspaces/session", "POST", key="synthetic-proxy-qa-project"
        )
        release.require(code == 200, "Host proxy scheme was not trusted")
        cookie = SimpleCookie()
        cookie.load(headers["Set-Cookie"])
        item = cookie["mywave_project_session"]
        release.require(
            item["secure"] and item["httponly"] and item["samesite"] == "strict",
            "Cookie flags failed",
        )
        cookie_header = "mywave_project_session=" + item.value
        release.require(
            call("/api/workspaces/projects", cookie=cookie_header)[0] == 200,
            "Browser session failed through proxy",
        )
        release.require(
            call(
                "/api/workspaces/session",
                "POST",
                forwarded=False,
                key="synthetic-proxy-qa-project",
            )[0]
            == 400,
            "Unencrypted non-loopback login allowed",
        )
        release.require(
            call("/api/workspaces/session", "POST", key="synthetic-proxy-qa-legacy")[0]
            == 403,
            "Shared key accepted for login",
        )
        forged = """import json,urllib.request,urllib.error
req=urllib.request.Request(URL,method='POST',headers={'X-API-Key':'synthetic-proxy-qa-project','X-Forwarded-Proto':'https'})
try:
 with urllib.request.urlopen(req,timeout=10) as response: code=response.status
except urllib.error.HTTPError as error:code=error.code
print(json.dumps({'status':code}))
""".replace(
            "URL", repr("http://" + app + ":8080/api/workspaces/session")
        )
        result = json.loads(
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--pull",
                    "never",
                    "--name",
                    probe,
                    "--label",
                    label,
                    "--network",
                    network,
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,size=16m",
                    "--memory",
                    "128m",
                    "--memory-swap",
                    "128m",
                    "--cpus",
                    "0.25",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--entrypoint",
                    "python",
                    release.IMAGE,
                    "-c",
                    forged,
                ]
            )
        )
        release.require(result["status"] == 400, "Untrusted peer forged HTTPS")
        current = ops.inspect(ops.APP)
        release.require(
            current["Id"] == before["Id"] and current["Image"] == before["Image"],
            "Production changed during QA",
        )
        report.update(
            result="passed",
            full_entrypoint="app.main",
            secure_cookie="passed",
            trusted_host_proxy="passed",
            untrusted_forwarded_proto="denied_400",
            plain_http="denied_400",
            shared_key="denied_403",
            production_container_unchanged=True,
        )
    finally:
        for name in (probe, app):
            try:
                current = ops.inspect(name)
            except RuntimeError:
                continue
            release.require(
                current["Config"]["Labels"].get("mywave.console-proxy") == ident,
                "Container cleanup ownership mismatch",
            )
            run(["docker", "rm", "-f", "-v", name])
        try:
            n = json.loads(run(["docker", "network", "inspect", network]))[0]
        except RuntimeError:
            n = None
        if n:
            release.require(
                n["Labels"].get("mywave.console-proxy") == ident,
                "Network cleanup ownership mismatch",
            )
            run(["docker", "network", "rm", network])
        report["cleanup"] = "passed"
        (folder / "qualification.json").write_text(json.dumps(report, indent=2))
    if report.get("result") == "passed":
        ops.atomic_write(
            release.RUNTIME / "console-proxy-qualification.json",
            json.dumps(report, indent=2).encode(),
        )
    print(json.dumps({"evidence_directory": str(folder), **report}, indent=2))


if __name__ == "__main__":
    main()
