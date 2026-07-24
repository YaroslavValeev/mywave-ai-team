# app/runners/cursor_runner — запуск Cursor CLI (headless) в sandbox
# Сценарий: получил задачу → открыл workspace → внёс правки → тесты → PR.
# Конфиг: docs/CURSOR-RUNNER.md

from app.runners.cursor_runner.local_env import merge_gateway_secrets_into_env
from app.runners.cursor_runner.runner import (
    build_cursor_argv,
    get_runner_config,
    resolve_cursor_binary,
    run_cursor_cli,
    run_cursor_cli_argv,
)
from app.runners.cursor_runner.sdk_runner import build_task_prompt, run_cursor_sdk_agent
from app.runners.cursor_runner.win_os_shim import ensure_windows_os_blocking_shim

__all__ = [
    "merge_gateway_secrets_into_env",
    "resolve_cursor_binary",
    "build_cursor_argv",
    "run_cursor_cli",
    "run_cursor_cli_argv",
    "get_runner_config",
    "run_cursor_sdk_agent",
    "build_task_prompt",
    "ensure_windows_os_blocking_shim",
]
