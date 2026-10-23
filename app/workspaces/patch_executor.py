"""Scoped patch -> isolated tests -> PR. No legacy repository, runner or credentials."""

from contextlib import contextmanager
from datetime import datetime
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.storage.models import (
    AuditEvent,
    Decision,
    Handoff,
    ProjectAccessGrant,
    Run,
    Task,
    WorkspaceMembership,
)
from app.storage.repositories import get_engine
from app.workspaces.access import Scope, ScopedRepository, ScopeDenied

PROFILE_ENV = "WORKSPACE_PATCH_PROFILES_JSON"
PROPOSAL = "SCOPED_PATCH_V1"
MAX_PATCH = 200_000


class ExecutionConflict(ValueError):
    pass


def require(value, message):
    if not value:
        raise ExecutionConflict(message)


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def profiles(scope):
    require(
        os.getenv("WORKSPACE_PATCH_EXECUTION_ENABLED", "false") == "true",
        "Scoped patch execution is disabled",
    )
    try:
        values = json.loads(os.getenv(PROFILE_ENV, "[]"))
        if not isinstance(values, list):
            raise ValueError()
        found = {}
        roots = []
        credential_scopes = {}
        for value in values:
            if set(value) != {
                "id",
                "workspace_id",
                "project_id",
                "workspace_path",
                "repository",
                "validation_image",
                "token_env",
            }:
                raise ValueError()
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value["id"]):
                raise ValueError()
            if any(
                type(value[k]) is not int or value[k] < 1
                for k in ("workspace_id", "project_id")
            ):
                raise ValueError()
            if not re.fullmatch(r"[\w.-]+/[\w.-]+", value["repository"]):
                raise ValueError()
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", value["validation_image"]):
                raise ValueError()
            if not re.fullmatch(
                r"WORKSPACE_EXECUTION_TOKEN_[A-Z0-9_]+", value["token_env"]
            ):
                raise ValueError()
            if (
                not isinstance(value["workspace_path"], str)
                or not Path(value["workspace_path"]).is_absolute()
            ):
                raise ValueError()
            if value["id"] in found:
                raise ValueError()
            path = Path(value["workspace_path"]).resolve()
            if any(path.is_relative_to(p) or p.is_relative_to(path) for p in roots):
                raise ValueError()
            roots.append(path)
            token = os.getenv(value["token_env"], value["token_env"])
            bound_scope = (value["workspace_id"], value["project_id"])
            if token in credential_scopes and credential_scopes[token] != bound_scope:
                raise ValueError()
            credential_scopes[token] = bound_scope
            found[value["id"]] = value
        return {
            k: v
            for k, v in found.items()
            if v["workspace_id"] == scope.workspace_id
            and v["project_id"] == scope.project_id
        }
    except (ValueError, TypeError, KeyError):
        raise ExecutionConflict("Scoped executor configuration is invalid") from None


def profile(scope, name):
    value = profiles(scope).get(name)
    require(value is not None, "No approved scoped executor profile")
    token = os.getenv(value["token_env"], "")
    shared = [os.getenv(k) for k in ("GH_TOKEN", "GITHUB_TOKEN", "OWNER_API_KEY")]
    shared += [v for k, v in os.environ.items() if k.startswith("WORKSPACE_KEY_")]
    require(
        bool(token) and token not in shared,
        "A separate project GitHub credential is required",
    )
    return value, digest({**value, "credential_sha256": digest(token.encode())})


def environment(token=None, home=None):
    # Never merge gateway, production, dotenv or process-wide application settings.
    value = {
        k: os.environ[k]
        for k in (
            "PATH",
            "SystemRoot",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "TMP",
            "TEMP",
            "LANG",
        )
        if k in os.environ
    }
    value.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_OPTIONAL_LOCKS="0",
        GH_PROMPT_DISABLED="1",
    )
    if home:
        value.update(HOME=str(home), USERPROFILE=str(home), GH_CONFIG_DIR=str(home))
    if token:
        value["GH_TOKEN"] = token
    return value


def command(args, *, cwd=None, data=None, env=None, timeout=60):
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            input=data,
            env=env or environment(),
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ExecutionConflict(
            "Scoped executor command unavailable or timed out"
        ) from None
    # Raw stderr may contain credentials, source contents or personal data.
    require(result.returncode == 0, "Scoped executor command failed")
    return result.stdout


def git(root, *args, data=None, token=None, home=None):
    flags = [
        "git",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.sshCommand=false",
        "-c",
        "http.followRedirects=false",
        "-c",
        "credential.helper=",
        "-c",
        "credential.https://github.com.helper=!gh auth git-credential",
    ]
    return command([*flags, *args], cwd=root, data=data, env=environment(token, home))


def checkout(value):
    raw = Path(value["workspace_path"])
    root = raw.resolve()
    require(
        root.is_dir() and not any(p.is_symlink() for p in (raw, *raw.parents)),
        "Execution checkout is absent or uses symlinks",
    )
    try:
        approved_roots = json.loads(os.getenv("WORKSPACE_PATCH_ROOTS_JSON", "[]"))
        require(
            isinstance(approved_roots, list)
            and all(
                isinstance(p, str) and Path(p).is_absolute() for p in approved_roots
            ),
            "Scoped checkout roots are invalid",
        )
        require(
            any(root.is_relative_to(Path(p).resolve()) for p in approved_roots),
            "Checkout is outside dedicated scoped roots",
        )
        legacy = json.loads(os.getenv("EXECUTION_ALLOWED_ROOTS_JSON", "[]"))
        require(isinstance(legacy, list), "Legacy checkout roots are invalid")
        legacy += [
            p for p in os.getenv("EXECUTION_ALLOWED_ROOTS", "").split(os.pathsep) if p
        ]
        blocked = [
            Path.cwd().resolve(),
            Path(os.getenv("ARTIFACTS_DIR", "app/artifacts")).resolve(),
        ]
        blocked += [Path(p).resolve() for p in legacy if isinstance(p, str)]
        require(
            not any(root.is_relative_to(p) or p.is_relative_to(root) for p in blocked),
            "Scoped checkout overlaps application, artifacts or legacy execution",
        )
    except (ValueError, TypeError):
        raise ExecutionConflict("Scoped checkout roots are invalid") from None
    require(
        (root / ".git").is_dir() and not (root / ".git").is_symlink(),
        "A separate execution clone is required",
    )
    require(
        Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        == root,
        "Execution path must be a repository root",
    )
    # A checkout must not supply credential-bearing URLs, command filters or hooks.
    allowed = {
        "core.repositoryformatversion",
        "core.filemode",
        "core.bare",
        "core.logallrefupdates",
        "core.ignorecase",
        "core.symlinks",
        "core.autocrlf",
        "core.precomposeunicode",
        "user.name",
        "user.email",
        "remote.origin.url",
        "remote.origin.fetch",
    }
    keys = git(root, "config", "--local", "--name-only", "--list").decode().splitlines()
    require(
        all(
            k in allowed or re.fullmatch(r"branch\.[\w/.-]+\.(remote|merge)", k)
            for k in keys
        ),
        "Execution clone has unsupported local Git configuration",
    )
    require(
        not git(root, "status", "--porcelain", "--untracked-files=all").strip(),
        "Execution checkout is dirty; existing changes were preserved",
    )
    require(
        git(root, "remote", "get-url", "origin").decode().strip()
        == "https://github.com/" + value["repository"] + ".git",
        "Repository differs from profile",
    )
    return root, git(root, "rev-parse", "HEAD").decode().strip()


def task_row(repo, task_id, *, write=False):
    repo._authorize("write" if write else "read")
    query = (
        repo._tasks()
        .where(Task.id == task_id)
        .execution_options(populate_existing=True)
    )
    row = repo.session.scalar(query.with_for_update() if write else query)
    if row is None:
        raise ScopeDenied("Scoped access denied")
    return row


def event(repo, task_id, name, **payload):
    repo.session.add(
        AuditEvent(
            task_id=task_id,
            event_type=name,
            payload_json={
                "workspace_id": repo.scope.workspace_id,
                "project_id": repo.scope.project_id,
                "principal_id": repo.scope.principal_id,
                **payload,
            },
        )
    )


def latest(repo, task_id):
    return repo.session.scalar(
        select(Handoff)
        .where(Handoff.task_id == task_id, Handoff.step_name == PROPOSAL)
        .order_by(Handoff.id.desc())
        .limit(1)
    )


def material(task, repo, value, fingerprint, patch, base):
    return {
        "task_id": task.id,
        "workspace_id": repo.scope.workspace_id,
        "project_id": repo.scope.project_id,
        "version": task.version,
        "owner_text_sha256": digest(task.owner_text.encode()),
        "profile_id": value["id"],
        "validation_image": value["validation_image"],
        "profile_sha256": fingerprint,
        "base_sha": base,
        "patch_sha256": digest(patch),
        "repository": value["repository"],
        "validation": "python -m pytest tests/ -q; isolated Docker; no network or secrets",
        "merge_allowed": False,
        "deploy_allowed": False,
    }


def prepare(repo, task_id, profile_id, patch_text):
    task = task_row(repo, task_id, write=True)
    require(
        task.status in {"NEW", "REWORK", "EXECUTION_FAILED"},
        "Task cannot accept a new patch in this status",
    )
    patch = patch_text.encode("utf-8")
    require(
        0 < len(patch) <= MAX_PATCH and b"\x00" not in patch,
        "Invalid patch size or encoding",
    )
    from app.shared.redaction import API_KEY_PATTERN, TOKEN_PATTERN

    require(
        not API_KEY_PATTERN.search(patch_text) and not TOKEN_PATTERN.search(patch_text),
        "Patch may contain secrets; remove credentials before review",
    )
    require(
        not re.search(
            r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN .*PRIVATE KEY-----)",
            patch_text,
        ),
        "Patch may contain a private credential",
    )
    require(
        not any(
            value.encode() in patch
            for key, value in os.environ.items()
            if len(value) >= 12
            and any(
                word in key
                for word in ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "WORKSPACE_KEY_")
            )
        ),
        "Patch contains a configured credential",
    )
    value, fingerprint = profile(repo.scope, profile_id)
    root, base = checkout(value)
    git(root, "apply", "--check", "-", data=patch)
    plan = material(task, repo, value, fingerprint, patch, base)
    payload = {
        "plan": plan,
        "sha256": digest(plan),
        "patch_base64": base64.b64encode(patch).decode(),
    }
    repo.session.add(
        Handoff(
            task_id=task_id,
            step_index=task.version,
            step_name=PROPOSAL,
            payload_json=payload,
        )
    )
    task.status = "WAIT_OWNER"
    task.summary = "Patch подготовлен. Тесты и создание PR ещё не запускались."
    event(repo, task_id, "scoped_patch_prepared", proposal_sha256=payload["sha256"])
    repo.session.commit()
    return {"status": task.status, "plan": plan, "proposal_sha256": payload["sha256"]}


def owner(repo):
    for model, field, ident in (
        (
            WorkspaceMembership,
            WorkspaceMembership.workspace_id,
            repo.scope.workspace_id,
        ),
        (ProjectAccessGrant, ProjectAccessGrant.project_id, repo.scope.project_id),
    ):
        role = repo.session.scalar(
            select(model.role).where(
                field == ident, model.principal_id == repo.scope.principal_id
            )
        )
        if role != "owner":
            raise ScopeDenied("Scoped access denied")


def checked(repo, task, proposal_sha256):
    handoff = latest(repo, task.id)
    require(handoff is not None, "No prepared scoped patch")
    blob = handoff.payload_json
    require(
        blob["sha256"] == proposal_sha256 == digest(blob["plan"]),
        "Proposal changed; review again",
    )
    value, fingerprint = profile(repo.scope, blob["plan"]["profile_id"])
    patch = base64.b64decode(blob["patch_base64"], validate=True)
    require(
        material(task, repo, value, fingerprint, patch, blob["plan"]["base_sha"])
        == blob["plan"],
        "Task, profile or credential changed; prepare again",
    )
    return blob, value, patch


def decide(repo, task_id, proposal_sha256, decision):
    task = task_row(repo, task_id, write=True)
    owner(repo)
    require(task.status == "WAIT_OWNER", "Task is not waiting for owner review")
    checked(repo, task, proposal_sha256)
    require(decision in {"approve", "rework"}, "Unknown decision")
    repo.session.add(
        Decision(
            task_id=task_id,
            decision=decision,
            owner_approval=decision == "approve",
            rationale=json.dumps(
                {
                    "proposal_sha256": proposal_sha256,
                    "principal_id": repo.scope.principal_id,
                    "workspace_id": repo.scope.workspace_id,
                    "project_id": repo.scope.project_id,
                }
            ),
        )
    )
    task.status = "EXECUTION_READY" if decision == "approve" else "REWORK"
    if decision == "rework":
        task.version += 1
        task.rework_cycles += 1
    event(repo, task_id, "scoped_patch_" + decision, proposal_sha256=proposal_sha256)
    repo.session.commit()
    return {"status": task.status}


def approved(repo, task, sha):
    result = checked(repo, task, sha)
    decision = repo.session.scalar(
        select(Decision)
        .where(Decision.task_id == task.id)
        .order_by(Decision.id.desc())
        .limit(1)
    )
    require(
        decision is not None
        and decision.owner_approval
        and decision.decision == "approve",
        "Owner approval required",
    )
    binding = json.loads(decision.rationale or "{}")
    require(
        binding.get("proposal_sha256") == sha
        and binding.get("workspace_id") == repo.scope.workspace_id
        and binding.get("project_id") == repo.scope.project_id,
        "Approval binding differs",
    )
    # Approval loses authority if the approving owner's membership/grant is revoked.
    approving_repo = ScopedRepository(
        repo.session,
        Scope(binding["principal_id"], repo.scope.workspace_id, repo.scope.project_id),
    )
    approving_repo._authorize("write")
    owner(approving_repo)
    return result


def start(repo, task_id, sha):
    task = task_row(repo, task_id, write=True)
    require(task.status == "EXECUTION_READY", "Task is not ready for execution")
    _, value, _ = approved(repo, task, sha)
    run_id = uuid.uuid4().hex
    # CAS also protects concurrent SQLite callers; PostgreSQL additionally locks the row.
    changed = repo.session.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.status == "EXECUTION_READY",
            Task.version == task.version,
        )
        .values(status="EXECUTING")
    )
    require(changed.rowcount == 1, "Execution was already claimed")
    repo.session.add(
        Run(
            run_id=run_id,
            task_id=task_id,
            orchestrator="scoped_patch_v1",
            source="scoped_project",
            state="running",
            phase="queued",
            current_step=value["id"],
            message=json.dumps(
                {"proposal_sha256": sha, "principal_id": repo.scope.principal_id}
            ),
            started_at=datetime.utcnow(),
            is_active=True,
        )
    )
    event(repo, task_id, "scoped_execution_queued", run_id=run_id, proposal_sha256=sha)
    repo.session.commit()
    return run_id


@contextmanager
def locked(root, run_id):
    path = root / ".git" / "mywave-scoped-execution.lock"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ExecutionConflict(
            "Execution clone is locked; owner recovery required"
        ) from None
    try:
        os.write(descriptor, run_id.encode())
        yield
    finally:
        os.close(descriptor)
        # Never remove somebody else's lock following a rename/replacement.
        if path.is_file() and not path.is_symlink() and path.read_text() == run_id:
            path.unlink()


def credential_path(path):
    name = path.name.lower()
    return (
        name
        in {".env", "credentials.json", "service_account.json", "id_rsa", "id_ed25519"}
        or (
            name.startswith(".env.")
            and name not in {".env.example", ".env.sample", ".env.template"}
        )
        or (name.startswith("client_secret") and name.endswith(".json"))
    )


def sandbox(root, value, patch):
    """Only a Git archive and approved bytes enter the disposable validation tree."""
    with tempfile.TemporaryDirectory(prefix="mywave-scoped-validation-") as temp:
        image = json.loads(
            command(["docker", "image", "inspect", value["validation_image"]])
        )[0]
        require(
            (image["Config"].get("Labels") or {}).get("mywave.scoped-validation")
            == "true",
            "A dedicated qualified validation image is required",
        )
        forbidden = (
            "TOKEN",
            "PASSWORD",
            "SECRET",
            "API_KEY",
            "WORKSPACE_KEY_",
            "CREDENTIAL",
            "DATABASE_URL",
            "REDIS_URL",
        )
        require(
            not any(
                any(word in entry.split("=", 1)[0].upper() for word in forbidden)
                and entry.split("=", 1)[-1]
                for entry in image["Config"].get("Env", [])
                if "=" in entry
            ),
            "Validation image contains credential environment variables",
        )
        temp = Path(temp)
        archive = temp / "source.tar"
        archive.write_bytes(git(root, "archive", "HEAD"))
        tree = temp / "tree"
        tree.mkdir()
        with tarfile.open(archive) as source:
            for item in source.getmembers():
                path = Path(item.name)
                require(
                    not path.is_absolute()
                    and ".." not in path.parts
                    and (item.isfile() or item.isdir())
                    and not item.name.startswith(".git/"),
                    "Validation source contains unsupported links or files",
                )
                require(
                    not credential_path(path),
                    "Validation source contains a credential file",
                )
            source.extractall(tree, filter="data")
        git(tree, "apply", "--check", "-", data=patch)
        git(tree, "apply", "-", data=patch)
        paths = [tree, *tree.rglob("*")]
        require(not any(p.is_symlink() for p in paths), "Patch introduces symlinks")
        require(
            not any(credential_path(p) for p in paths),
            "Patch introduces a credential file",
        )
        original = {
            str(p.relative_to(tree)): digest(p.read_bytes())
            for p in paths
            if p.is_file()
        }
        # Non-root sandbox user can write only this disposable, secret-free copy.
        for path in paths:
            path.chmod(0o777 if path.is_dir() or path.stat().st_mode & 0o111 else 0o666)
        name = "mywave-scoped-test-" + uuid.uuid4().hex
        args = [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--name",
            name,
            "--label",
            "mywave.scoped-test=" + name,
            "--network",
            "none",
            "--read-only",
            "--user",
            "65534:65534",
            "--tmpfs",
            "/tmp:rw,size=128m,mode=1777",
            "--memory",
            "512m",
            "--memory-swap",
            "512m",
            "--cpus",
            "0.75",
            "--pids-limit",
            "128",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--mount",
            "type=bind,source=" + str(tree) + ",target=/workspace",
            "--workdir",
            "/workspace",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "DATABASE_URL=sqlite:///:memory:",
            "-e",
            "OWNER_API_KEY=isolated-test-only",
            "-e",
            "TELEGRAM_POLLING_ENABLED=false",
            "-e",
            "ORCHESTRATION_ENGINE=rule_based",
            "-e",
            "PYTHONPATH=/workspace:/workspace/packages/shared-core:/workspace/packages/agents-http-client",
            "--entrypoint",
            "python",
            value["validation_image"],
            "-m",
            "pytest",
            "tests/",
            "-q",
            "-p",
            "no:cacheprovider",
        ]
        try:
            command(args, timeout=360)
            require(
                all(
                    (tree / name).is_file()
                    and not (tree / name).is_symlink()
                    and digest((tree / name).read_bytes()) == sha
                    for name, sha in original.items()
                ),
                "Tests changed the approved source",
            )
        finally:
            # A timeout can leave a Docker container alive; delete only our labelled container.
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "mywave.scoped-test"}}',
                    name,
                ],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.decode().strip() == name:
                command(["docker", "rm", "-f", name])


def run_job(scope, task_id, run_id, sha):
    """Every external phase reacquires live task/actor/approver permissions in SQL."""
    active_phase = "preflight"

    def phase(name, action):
        nonlocal active_phase
        active_phase = name
        with Session(get_engine()) as session:
            repo = ScopedRepository(session, scope)
            task = task_row(repo, task_id, write=True)
            require(task.status == "EXECUTING", "Execution no longer authorized")
            run = session.scalar(
                select(Run)
                .where(
                    Run.task_id == task_id,
                    Run.run_id == run_id,
                    Run.is_active.is_(True),
                )
                .with_for_update()
            )
            require(run is not None, "Execution claim is no longer active")
            blob, value, patch = approved(repo, task, sha)
            run.phase = name
            result = action(repo, task, value, patch, blob)
            event(repo, task_id, "scoped_execution_" + name, run_id=run_id)
            session.commit()
            return result

    try:
        value = phase("preflight", lambda repo, task, v, patch, blob: v)
        root = Path(value["workspace_path"]).resolve()
        with locked(root, run_id), tempfile.TemporaryDirectory(
            prefix="mywave-scoped-git-"
        ) as home:
            branch = "feature/scoped-task-" + str(task_id) + "-" + run_id[:12]

            def access(repo, task, value, patch, blob):
                checkout(value)
                token = os.environ[value["token_env"]]
                writable = command(
                    [
                        "gh",
                        "api",
                        "repos/" + value["repository"],
                        "--jq",
                        ".permissions.push",
                    ],
                    env=environment(token, home),
                ).strip()
                require(
                    writable == b"true",
                    "Project credential has no repository write permission",
                )
                git(
                    root,
                    "push",
                    "--dry-run",
                    "origin",
                    "HEAD:refs/heads/" + branch,
                    token=token,
                    home=home,
                )

            phase("access", access)

            def validate(repo, task, value, patch, blob):
                _, base = checkout(value)
                require(
                    base == blob["plan"]["base_sha"], "Base SHA changed; prepare again"
                )
                sandbox(root, value, patch)

            phase("validation", validate)

            def commit(repo, task, value, patch, blob):
                _, base = checkout(value)
                require(
                    base == blob["plan"]["base_sha"],
                    "Checkout changed during validation",
                )
                git(root, "checkout", "-b", branch)
                git(root, "apply", "--index", "-", data=patch)
                git(
                    root,
                    "commit",
                    "-m",
                    "feat: apply owner-approved scoped task " + str(task_id),
                )
                return git(root, "rev-parse", "HEAD").decode().strip()

            commit_sha = phase("commit", commit)

            def publish(repo, task, value, patch, blob):
                _, actual = checkout(value)
                require(
                    actual == commit_sha,
                    "Committed checkout changed before publication",
                )
                token = os.environ[value["token_env"]]
                git(
                    root,
                    "push",
                    "origin",
                    "HEAD:refs/heads/" + branch,
                    token=token,
                    home=home,
                )
                report = Path(home) / "report.md"
                report.write_text(
                    "Owner-approved scoped patch. Isolated tests passed.\n\nProposal SHA256: "
                    + sha
                    + "\n\nMerge and deployment require separate owner decisions.\n"
                )
                url = (
                    command(
                        [
                            "gh",
                            "pr",
                            "create",
                            "--repo",
                            value["repository"],
                            "--head",
                            branch,
                            "--base",
                            "main",
                            "--title",
                            "Scoped task " + str(task_id),
                            "--body-file",
                            str(report),
                        ],
                        cwd=root,
                        env=environment(token, home),
                    )
                    .decode()
                    .strip()
                )
                require(
                    re.fullmatch(
                        r"https://github\.com/"
                        + re.escape(value["repository"])
                        + r"/pull/[0-9]+",
                        url,
                    ),
                    "PR was not confirmed",
                )
                task.status, task.pr_url, task.commit_sha = (
                    "APPROVED_WAIT_MERGE",
                    url,
                    commit_sha,
                )
                task.summary = (
                    "Тесты пройдены, PR создан. Ожидается проверка и merge владельца."
                )
                run = repo.session.scalar(select(Run).where(Run.run_id == run_id))
                run.state, run.is_active, run.result_status = (
                    "completed",
                    False,
                    task.status,
                )
                run.finished_at = datetime.utcnow()

            phase("publish", publish)
    except Exception:
        # A failure must release the persistent claim even if the actor was revoked.
        # It never writes arbitrary exception text or touches another task/project.
        with Session(get_engine()) as session:
            run = session.scalar(
                select(Run)
                .where(
                    Run.run_id == run_id,
                    Run.task_id == task_id,
                    Run.orchestrator == "scoped_patch_v1",
                )
                .with_for_update()
            )
            if run is not None and run.is_active:
                task = session.scalar(
                    select(Task)
                    .where(
                        Task.id == task_id,
                        Task.workspace_id == scope.workspace_id,
                        Task.project_id == scope.project_id,
                    )
                    .with_for_update()
                )
                if task is not None and task.status == "EXECUTING":
                    task.status = "EXECUTION_FAILED"
                    task.summary = "Исполнение остановлено. Проверьте результат и рабочую копию перед повторным запуском."
                run.state, run.is_active = "failed", False
                run.phase = active_phase
                run.last_error = (
                    "Scoped execution failed; inspect the checkout before retrying."
                )
                run.finished_at = datetime.utcnow()
                event(
                    ScopedRepository(session, scope),
                    task_id,
                    "scoped_execution_failed",
                    run_id=run_id,
                )
                session.commit()


def snapshot(repo, task_id):
    task = task_row(repo, task_id)
    proposal = latest(repo, task_id)
    run = repo.session.scalar(
        select(Run)
        .where(Run.task_id == task_id, Run.orchestrator == "scoped_patch_v1")
        .order_by(Run.id.desc())
        .limit(1)
    )
    roles = [
        repo.session.scalar(
            select(model.role).where(
                field == ident, model.principal_id == repo.scope.principal_id
            )
        )
        for model, field, ident in (
            (
                WorkspaceMembership,
                WorkspaceMembership.workspace_id,
                repo.scope.workspace_id,
            ),
            (ProjectAccessGrant, ProjectAccessGrant.project_id, repo.scope.project_id),
        )
    ]
    return {
        "status": task.status,
        "can_approve": all(role == "owner" for role in roles),
        "proposal": (
            {
                "plan": proposal.payload_json["plan"],
                "proposal_sha256": proposal.payload_json["sha256"],
                "patch_text": base64.b64decode(
                    proposal.payload_json["patch_base64"]
                ).decode("utf-8"),
            }
            if proposal
            else None
        ),
        "run": (
            {
                "run_id": run.run_id,
                "state": run.state,
                "phase": run.phase,
                "is_active": run.is_active,
            }
            if run
            else None
        ),
        "pr_url": task.pr_url,
        "commit_sha": task.commit_sha,
        "summary": task.summary,
    }
