# app/runners/cursor_runner/runner.py — вызов Cursor CLI в workspace
# Секреты: через app.gateway; бинарь: CURSOR_CLI или `cursor` в PATH.

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
from pathlib import Path
from typing import Optional

from app.runners.cursor_runner.local_env import merge_gateway_secrets_into_env

logger = logging.getLogger(__name__)


def resolve_cursor_binary() -> str:
    """
    Путь к исполняемому файлу Cursor CLI.
    Приоритет: CURSOR_CLI → shutil.which('cursor') → shutil.which('cursor' на Windows с .exe).
    """
    explicit = (os.environ.get("CURSOR_CLI") or "").strip()
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return str(p.resolve())
        # если задано имя без пути — ищем в PATH
        w = shutil.which(explicit)
        if w:
            return w
        return explicit

    w = shutil.which("cursor")
    if w:
        return w
    if os.name == "nt":
        w = shutil.which("cursor.exe")
        if w:
            return w
    return "cursor"


def build_cursor_argv(command: str, *, binary: Optional[str] = None) -> list[str]:
    """
    Собрать argv для subprocess: [binary, ...args].
    Пустая command → ['--version'] (реальная проверка наличия CLI, не фиктивный --help).
    """
    exe = (binary or resolve_cursor_binary()).strip() or "cursor"
    raw = (command or "").strip()
    if not raw:
        return [exe, "--version"]
    # shlex: на Windows отключаем posix-режим для путей с обратными слешами
    posix = os.name != "nt"
    try:
        parts = shlex.split(raw, posix=posix)
    except ValueError as e:
        raise ValueError(f"Не удалось разобрать command: {e}") from e
    if not parts:
        return [exe, "--version"]
    # Первый токен уже указывает на бинарь cursor — не дублируем resolve_cursor_binary()
    first_name = Path(parts[0]).name.lower()
    if first_name in ("cursor", "cursor.exe"):
        return parts
    return [exe, *parts]


async def run_cursor_cli(
    workspace_path: str,
    command: str,
    env_override: Optional[dict] = None,
    timeout_sec: int = 300,
    *,
    inject_gateway_secrets: bool = True,
) -> tuple[int, str, str]:
    """
    Запуск Cursor CLI в workspace.

    command: строка аргументов для `cursor` (как в shell), например:
      'agent --print' или 'tunnel --help'
    Пустая строка → выполняется `cursor --version` (диагностика установки).

    Секреты: при inject_gateway_secrets=True подмешиваются GH_TOKEN / OPENAI_API_KEY из gateway,
    если их ещё нет в окружении (согласовано с app/config/gateway.yaml).

    Returns: (exit_code, stdout, stderr)
    """
    workdir = Path(workspace_path)
    if not workdir.exists():
        return 1, "", f"Workspace not found: {workspace_path}"

    env = merge_gateway_secrets_into_env(env_override) if inject_gateway_secrets else {**os.environ, **(env_override or {})}

    try:
        argv = build_cursor_argv(command)
    except ValueError as e:
        return 1, "", str(e)

    logger.info("Cursor CLI: cwd=%s argv=%s", workdir, _safe_argv_log(argv))

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workdir.resolve()),
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
        code = proc.returncode if proc.returncode is not None else -1
        return (
            code,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    except FileNotFoundError:
        bin_hint = argv[0] if argv else "cursor"
        logger.warning("Cursor CLI not found: %s", bin_hint)
        return (
            1,
            "",
            f"Cursor CLI not found: {bin_hint}. Установите Cursor, добавьте в PATH или задайте CURSOR_CLI.",
        )


def _safe_argv_log(argv: list[str]) -> list[str]:
    """Не логировать значения, похожие на длинные токены."""
    out = []
    for a in argv:
        if len(a) > 80 and all(c.isalnum() or c in "_-" for c in a):
            out.append(a[:12] + "…(redacted)")
        else:
            out.append(a)
    return out


async def run_cursor_cli_argv(
    workspace_path: str,
    argv: list[str],
    env_override: Optional[dict] = None,
    timeout_sec: int = 300,
    *,
    inject_gateway_secrets: bool = True,
) -> tuple[int, str, str]:
    """Запуск с готовым списком argv (без shell-разбора). Первый элемент — бинарник."""
    workdir = Path(workspace_path)
    if not workdir.exists():
        return 1, "", f"Workspace not found: {workspace_path}"
    if not argv:
        return 1, "", "argv пуст"
    env = merge_gateway_secrets_into_env(env_override) if inject_gateway_secrets else {**os.environ, **(env_override or {})}
    logger.info("Cursor CLI argv: cwd=%s cmd=%s", workdir, _safe_argv_log(list(argv)))
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workdir.resolve()),
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
        code = proc.returncode if proc.returncode is not None else -1
        return (
            code,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    except FileNotFoundError:
        return 1, "", f"Executable not found: {argv[0]}"


def get_runner_config() -> dict:
    """Конфиг runner из env."""
    binary = resolve_cursor_binary()
    return {
        "workspace": os.environ.get("CURSOR_WORKSPACE", "."),
        "timeout_sec": int(os.environ.get("CURSOR_RUNNER_TIMEOUT", "300")),
        "sandbox": os.environ.get("CURSOR_SANDBOX_DIR"),
        "cursor_binary": binary,
        "cursor_binary_exists": shutil.which(binary) is not None or Path(binary).is_file(),
    }
