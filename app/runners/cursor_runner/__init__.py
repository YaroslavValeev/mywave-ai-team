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

__all__ = [
    "merge_gateway_secrets_into_env",
    "resolve_cursor_binary",
    "build_cursor_argv",
    "run_cursor_cli",
    "run_cursor_cli_argv",
    "get_runner_config",
]
