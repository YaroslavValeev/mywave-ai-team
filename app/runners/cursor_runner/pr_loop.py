# app/runners/cursor_runner/pr_loop.py — PR-loop без merge (v0.2)
# Runner локально: GET task → git branch → apply → pytest → commit → push → PR → PATCH server.
# ЗАПРЕЩЕНО: gh pr merge, git merge в main. Только Owner мерджит вручную.
# v0.2.1: mode=manual|patch|cursor_agent (patch/cursor_agent reserved)

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, Literal, Optional

from app.shared import api_client
from app.runners.cursor_runner.local_env import merge_gateway_secrets_into_env

logger = logging.getLogger(__name__)

MERGE_FORBIDDEN = True  # Никогда не мерджим из Runner

RunnerMode = Literal["manual", "patch", "cursor_agent"]


def _run(cmd: list[str], cwd: Path, env: Optional[dict] = None, *, isolated_env: bool = False) -> tuple[int, str, str]:
    """Выполнить команду. Env согласован с gateway (GH/OPENAI при отсутствии в окружении)."""
    try:
        merged = dict(env or {}) if isolated_env else merge_gateway_secrets_into_env(env)
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            env=merged,
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"


def _validation_environment(workspace: Path) -> dict[str, str]:
    """Run checkout tests without production credentials, DB or live LLM settings."""
    environment = {
        key: os.environ[key]
        for key in ("PATH", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP", "LANG", "LC_ALL")
        if key in os.environ
    }
    environment.update({
        "DATABASE_URL": "sqlite:///:memory:",
        "OWNER_API_KEY": "test_key_for_execution_validation",
        "ORCHESTRATION_ENGINE": "rule_based",
        "TELEGRAM_POLLING_ENABLED": "false",
        "TELEGRAM_STAGE_NOTIFY": "false",
        "TELEGRAM_PROACTIVE_NOTIFY_ENABLED": "false",
        "PYTHONPATH": os.pathsep.join((str(workspace), str(workspace / "packages" / "shared-core"))),
    })
    return environment


def _build_dev_report(
    task_id: int,
    summary: str,
    changed_files: list[str],
    pytest_ok: bool,
    mode: RunnerMode = "manual",
    ci_url: Optional[str] = None,
) -> str:
    """Формирование DEV REPORT (v0.2.1: mode, CI status, Owner next steps)."""
    ci_status = "CI pending/unknown — Check Actions tab" if not ci_url else ci_url
    owner_steps = ""
    if mode == "manual":
        owner_steps = """
**Owner next steps (manual mode):**
1. Открой Cursor в workspace
2. Внеси правки по задаче (artifacts, handoffs)
3. `pytest -q` локально
4. `git add -A && git commit -m "fix: ..." && git push`
5. PR уже создан или создай вручную
"""
    return f"""## [DEV REPORT]

**task_id:** {task_id}
**mode:** {mode}
**что сделано:** {summary or "Changes applied"}
**изменённые файлы:** {", ".join(changed_files) or "-"}
**pytest:** {"✅ passed" if pytest_ok else "❌ failed"}
**ci_url:** {ci_status}
**как проверить:** Run `pytest -q`
**риски/сомнения:** -
{owner_steps}
---

## Чек-лист перед merge

- [ ] `pytest -q` проходит
- [ ] Нет секретов в коде
- [ ] Документация обновлена при необходимости

[END]
"""


async def run_pr_loop(
    task_id: int,
    workspace_path: str,
    apply_callback: Optional[Callable[[str, dict], None]] = None,
    mode: RunnerMode = "manual",
    *,
    task_data_override: Optional[dict] = None,
    task_update_callback: Optional[Callable[..., object]] = None,
    cancel_check: Optional[Callable[[], None]] = None,
    branch_name: Optional[str] = None,
) -> dict:
    """
    PR-loop: получить задачу → ветка → правки → тесты → commit → push → PR → PATCH.
    apply_callback(workspace_path, task_data) — опционально применить патч/изменения.
    Returns: {success, pr_url, commit_sha, ci_url, error}
    """
    workspace = Path(workspace_path)
    if not workspace.exists():
        return {"success": False, "error": f"Workspace not found: {workspace_path}"}

    if mode == "manual":
        return {
            "success": False,
            "mode": "manual",
            "requires_owner_action": True,
            "error": "Manual mode is evidence-only and cannot modify, commit or push a workspace.",
        }
    if mode not in ("patch", "cursor_agent"):
        return {"success": False, "error": f"Unsupported runner mode: {mode}"}
    if not callable(apply_callback):
        return {
            "success": False,
            "mode": mode,
            "error": "Executable mode requires an explicit apply_callback.",
        }

    if cancel_check:
        cancel_check()
    if task_data_override is None:
        task_data, err = api_client.task_get(task_id)
        if err or not task_data:
            return {"success": False, "error": err or "Task not found"}
    else:
        task_data = dict(task_data_override)

    resolved_branch_name = branch_name or f"chore/task-{task_id}"

    code, out, err_out = _run(["git", "status", "--porcelain"], workspace)
    if code != 0:
        return {"success": False, "error": f"git status failed: {err_out}"}
    if out.strip():
        return {
            "success": False,
            "error": "Workspace must be clean before execution; existing changes were not touched.",
        }

    merged_base = merge_gateway_secrets_into_env()
    gh_token = merged_base.get("GH_TOKEN") or merged_base.get("GITHUB_TOKEN")
    if not gh_token:
        return {
            "success": False,
            "pr_url": "",
            "commit_sha": "",
            "ci_url": "",
            "error": "GH_TOKEN not set; execution was not started.",
        }

    code, _, err_out = _run(["git", "checkout", "-b", resolved_branch_name], workspace)
    if code != 0:
        return {
            "success": False,
            "error": f"git branch creation failed; execution was not started: {err_out}",
        }

    try:
        apply_callback(str(workspace), task_data)
    except Exception as e:
        logger.exception("apply_callback failed")
        return {"success": False, "error": str(e)}
    if cancel_check:
        cancel_check()

    code, out, err_out = _run(["git", "status", "--porcelain"], workspace)
    if code != 0:
        return {"success": False, "error": f"git status after execution failed: {err_out}"}
    changed = [line.split(maxsplit=1)[-1] for line in out.strip().splitlines() if line.strip()]
    if not changed:
        return {"success": False, "error": "Executor produced no workspace changes."}

    code, pytest_out, pytest_err = _run(
        ["python", "-m", "pytest", "tests/", "-q", "--tb=short"],
        workspace,
        env=_validation_environment(workspace),
        isolated_env=True,
    )
    pytest_ok = code == 0
    if not pytest_ok:
        return {
            "success": False,
            "error": "Validation failed; commit and push were blocked.",
            "pytest_output": (pytest_out + "\n" + pytest_err)[-8000:],
            "changed_files": changed,
        }
    if cancel_check:
        cancel_check()

    repo = os.getenv("GITHUB_REPOSITORY", "YaroslavValeev/mywave-ai-team")
    report = _build_dev_report(task_id, task_data.get("summary", "")[:200], changed, pytest_ok, mode, None)
    report_path = workspace / "DEV_REPORT.md"
    report_path.write_text(report, encoding="utf-8")

    code, _, err_out = _run(["git", "add", "-A"], workspace)
    if code != 0:
        return {"success": False, "error": f"git add failed: {err_out}"}

    code, _, err_out = _run(["git", "commit", "-m", f"chore(task-{task_id}): DEV REPORT"], workspace)
    if code != 0 and "nothing to commit" not in err_out:
        return {"success": False, "error": f"git commit failed: {err_out}"}

    code, out, err_out = _run(["git", "rev-parse", "HEAD"], workspace)
    commit_sha = out.strip()[:12] if code == 0 else ""

    code, _, err_out = _run(["git", "push", "-u", "origin", resolved_branch_name], workspace)
    if code != 0:
        return {"success": False, "error": f"git push failed: {err_out}"}

    env = {**merged_base, "GH_TOKEN": gh_token}
    code, out, err_out = _run(
        ["gh", "pr", "create", "--title", f"[task-{task_id}] DEV REPORT", "--body", report, "--base", "main"],
        workspace,
        env=env,
    )
    pr_url = ""
    pr_number = None
    if code == 0 and "http" in out:
        for line in out.split("\n"):
            if "http" in line and "github.com" in line:
                pr_url = line.strip()
                if "/pull/" in pr_url:
                    try:
                        pr_number = int(pr_url.split("/pull/")[-1].split("/")[0].split("?")[0])
                    except (ValueError, IndexError):
                        pass
                break
    if not pr_url:
        return {
            "success": False,
            "commit_sha": commit_sha,
            "error": f"GitHub PR creation failed: {err_out or 'no PR URL returned'}",
        }

    if repo:
        ci_url_val = f"https://github.com/{repo}/actions?query=branch%3A{resolved_branch_name}"
    else:
        ci_url_val = ""

    update_task = task_update_callback or api_client.task_update
    update_task(
        task_id,
        status="APPROVED_WAIT_MERGE",
        pr_url=pr_url,
        commit_sha=commit_sha,
        ci_url=ci_url_val or None,
    )

    return {"success": True, "pr_url": pr_url, "commit_sha": commit_sha, "ci_url": ci_url_val, "error": None}
