# app/runners/cursor_runner/runner.py — вызов Cursor CLI
# Безопасность: через gateway, минимальные права, sandbox.

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


async def run_cursor_cli(
    workspace_path: str,
    command: str,
    env_override: Optional[dict] = None,
    timeout_sec: int = 300,
) -> tuple[int, str, str]:
    """
    Запуск Cursor CLI в workspace.
    command: например "apply patch" или custom script.
    Returns: (exit_code, stdout, stderr)
    """
    env = os.environ.copy()
    if env_override:
        env.update(env_override)

    # TODO: cursor CLI path, sandbox, capability injection
    # Cursor CLI: cursor --help (headless mode)
    cmd = ["cursor", "--help"]  # placeholder
    workdir = Path(workspace_path)
    if not workdir.exists():
        return 1, "", f"Workspace not found: {workspace_path}"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workdir,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, "", "Timeout"
        return proc.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
    except FileNotFoundError:
        logger.warning("Cursor CLI not found in PATH")
        return 1, "", "Cursor CLI not installed or not in PATH"


def get_runner_config() -> dict:
    """Конфиг runner из env/config."""
    return {
        "workspace": os.environ.get("CURSOR_WORKSPACE", "."),
        "timeout_sec": int(os.environ.get("CURSOR_RUNNER_TIMEOUT", "300")),
        "sandbox": os.environ.get("CURSOR_SANDBOX_DIR"),
    }
