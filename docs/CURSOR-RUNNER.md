# Cursor Runner — PR-loop (v0.2)

Сценарий: получил задачу с сервера → git branch → правки → pytest → commit → push → PR → PATCH серверу. **Merge только Owner вручную.**

## Архитектура

- **Server (Timeweb):** Orchestrator + DB + Dashboard + HTTP API.
- **Local (Owner machine):** Runner запускается локально, выполняет git/pytest/PR.
- **Gate:** Merge только Owner. Runner **никогда не мерджит**.

## Переменные окружения (локально)

| Переменная | Описание |
|------------|----------|
| `OWNER_API_KEY` | Ключ для API |
| `MYWAVE_BASE_URL` | `https://agm.mywavetreaning.ru` |
| `GH_TOKEN` или `GITHUB_TOKEN` | Для `gh pr create` |
| `GITHUB_REPOSITORY` | owner/repo |
| `CURSOR_WORKSPACE` | Путь к workspace (default: .) |

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

## Что делает Runner

1. GET /api/tasks/{id} + /api/tasks/{id}/artifacts
2. `git checkout -b chore/task-{id}`
3. (опционально) apply_callback — применить патч
4. `pytest tests/ -q`
5. Формирует DEV_REPORT.md
6. `git commit && git push`
7. `gh pr create` (если GH_TOKEN задан)
8. PATCH /api/tasks/{id} — status=WAIT_OWNER, pr_url, commit_sha
9. Owner получает Telegram с PR ссылкой и кнопками

## Запрещено

- `gh pr merge`, `git merge main` — только Owner вручную.
- После merge Owner нажимает «I merged» → статус DONE.

---

## Режимы (v0.2.1)

| mode | Описание | Статус |
|------|----------|--------|
| `manual` | Owner вносит правки в Cursor вручную | **default**, production |
| `patch` | Авто-применение патча | reserved (v0.3) |
| `cursor_agent` | Cursor Agent CLI | reserved (v0.3) |

### Manual flow (по умолчанию)

1. Runner: GET task → git branch → pytest → DEV_REPORT → commit → push → PR → PATCH.
2. Runner НЕ вносит правки в код — только подготавливает ветку и отчёт.
3. Owner: открыть Cursor, внести правки по задаче, `pytest -q`, `git add && commit && push`.
4. PR уже создан runner'ом (если GH_TOKEN задан) или Owner создаёт вручную.
5. DEV_REPORT содержит блок **Owner next steps** с пошаговой инструкцией.
