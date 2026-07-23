# Cursor Runner — PR-loop (v0.2)

Сценарий: получил задачу с сервера → git branch → правки → pytest → commit → push → PR → PATCH серверу. **Merge только Owner вручную.**

## Архитектура

- **Server (Timeweb):** Orchestrator + DB + Dashboard + HTTP API.
- **Local (Owner machine):** Runner запускается локально, выполняет git/pytest/PR.
- **Gate:** Merge только Owner. Runner **никогда не мерджит**.
- **Gateway:** секреты для GitHub и OpenAI согласованы с `app/config/gateway.yaml` — локальные subprocess получают `GH_TOKEN` / `OPENAI_API_KEY` через `merge_gateway_secrets_into_env()`, если переменные ещё не заданы в окружении (не перезаписывают явный `.env` / shell).

## Переменные окружения (локально)

### API и git / GitHub


| Переменная                    | Описание                                                      |
| ----------------------------- | ------------------------------------------------------------- |
| `OWNER_API_KEY`               | Ключ для API                                                  |
| `MYWAVE_BASE_URL`             | `https://agm.mywavewake.ru`                                   |
| `GH_TOKEN` или `GITHUB_TOKEN` | Для `gh pr create` (если не заданы — см. gateway ниже)        |
| `GITHUB_REPOSITORY`           | owner/repo                                                    |
| `OPENAI_API_KEY`              | Опционально для сценариев с LLM (если не задан — см. gateway) |


### Cursor CLI и workspace


| Переменная              | Описание                                                                                                          |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `CURSOR_CLI`            | Явный путь или имя бинарника Cursor CLI. Если не задан: ищется `cursor` в `PATH` (на Windows также `cursor.exe`). |
| `CURSOR_WORKSPACE`      | Путь к workspace для `get_runner_config()` (default: `.`)                                                         |
| `CURSOR_RUNNER_TIMEOUT` | Таймаут секунд для async-вызова CLI (default: `300`)                                                              |
| `CURSOR_SANDBOX_DIR`    | Опционально: каталог sandbox (прокидывается в конфиг runner)                                                      |


**Gateway-подстановка:** функция `merge_gateway_secrets_into_env()` дополняет окружение токенами из `app.gateway.secrets` (GitHub / OpenAI) только если соответствующих переменных ещё нет. Это совпадает с capability `scopes.github` / `scopes.openai` в `gateway.yaml` и не противоречит выдаче секретов через Control API.

## Запуск PR-loop

```python
import asyncio
from app.runners.cursor_runner.pr_loop import run_pr_loop

result = asyncio.run(run_pr_loop(
    task_id=42,
    workspace_path="/path/to/repo",
    apply_callback=None,  # или функция(workspace_path, task_data)
))
# result: {success, pr_url, commit_sha, ci_url, error}
```

Внутри PR-loop все вызовы `subprocess` используют `merge_gateway_secrets_into_env()`, чтобы `gh` и прочие команды видели те же токены, что и остальной локальный рантайм.

## Cursor CLI (`runner.py`)

Асинхронный вызов настоящего бинарника Cursor (не заглушка):

- `**resolve_cursor_binary()**` — приоритет: `CURSOR_CLI` → `shutil.which("cursor")` → на Windows `cursor.exe` → строка `"cursor"` для сообщений об ошибке.
- `**build_cursor_argv(command, binary=...)**` — собирает `argv`: `[exe, ...args]`. Строка `command` разбирается через `shlex` (`posix=False` на Windows для путей с `\`).
- **Пустая `command`** — выполняется `**cursor --version**` (проверка установки CLI), а не фиктивный `--help`.
- Если первый токен команды уже `cursor` / `cursor.exe`, список аргументов не дублирует бинарник.
- `**run_cursor_cli` / `run_cursor_cli_argv**` — `asyncio.create_subprocess_exec`, таймаут, лог argv с редактированием длинных токенов. По умолчанию `inject_gateway_secrets=True` (см. выше).

Диагностика без запуска полного цикла:

```python
from app.runners.cursor_runner import get_runner_config, build_cursor_argv

cfg = get_runner_config()
# cursor_binary, cursor_binary_exists, workspace, timeout_sec, sandbox
argv = build_cursor_argv("")  # → ['…/cursor', '--version']
```

Публичный API пакета (`app.runners.cursor_runner`): `merge_gateway_secrets_into_env`, `resolve_cursor_binary`, `build_cursor_argv`, `run_cursor_cli`, `run_cursor_cli_argv`, `get_runner_config`.

## Проверка состояния (Dashboard / API)

Сводный health приложения: `**GET /api/system/health**` (с заголовком `X-API-Key`, как для остального Dashboard API). В ответе поле `**checks.runner**`:

- `**ok**` — заданы `GITHUB_REPOSITORY` и GitHub-токен (`GH_TOKEN` / `GITHUB_TOKEN` в env **или** через gateway); в `message` добавлена подсказка по бинарнику Cursor (путь и найден ли в PATH).
- `**warn`** — не хватает репозитория или токена для PR-интеграции; подсказка по Cursor всё равно показывается, если модуль runner доступен.

Так команда видит на сервере «готов ли сценарий PR-loop на стороне конфигурации»; сам бинарник Cursor проверяется на той машине, где вы реально запускаете `pr_loop` / CLI.

## Что делает Runner

1. GET /api/tasks/{id} + /api/tasks/{id}/artifacts
2. `git checkout -b chore/task-{id}`
3. (опционально) apply_callback — применить патч
4. `pytest tests/ -q`
5. Формирует DEV_REPORT.md
6. `git commit && git push`
7. `gh pr create` (если доступен токен: `GH_TOKEN` / `GITHUB_TOKEN` в окружении или через gateway)
8. PATCH /api/tasks/{id} — status=WAIT_OWNER, pr_url, commit_sha
9. Owner получает Telegram с PR ссылкой и кнопками

## Запрещено

- `gh pr merge`, `git merge main` — только Owner вручную.
- После merge Owner нажимает «I merged» → статус DONE.

---

## Режимы (v0.2.1)


| mode           | Описание                             | Статус                  |
| -------------- | ------------------------------------ | ----------------------- |
| `manual`       | Owner вносит правки в Cursor вручную | **default**, production |
| `patch`        | Авто-применение патча                | reserved (v0.3)         |
| `cursor_agent` | Cursor Agent CLI                     | reserved (v0.3)         |


### Manual flow (по умолчанию)

1. Runner: GET task → git branch → pytest → DEV_REPORT → commit → push → PR → PATCH.
2. Runner НЕ вносит правки в код — только подготавливает ветку и отчёт.
3. Owner: открыть Cursor, внести правки по задаче, `pytest -q`, `git add && commit && push`.
4. PR уже создан runner'ом (если доступен GitHub-токен, см. выше) или Owner создаёт вручную.
5. DEV_REPORT содержит блок **Owner next steps** с пошаговой инструкцией.

