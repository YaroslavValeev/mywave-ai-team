# Аудит полноты: каналы использования

Snapshot: 2026-04-08 (синхронизировано с кодом репозитория).

Проверка: Telegram, Dashboard HTML, Control API, MCP (Cursor), Office UI.

---

## 1. Telegram (основной MVP-канал)

| Требование | Статус | Примечание |
|------------|--------|------------|
| TELEGRAM_BOT_TOKEN | ✅ | .env |
| OWNER_CHAT_ID | ✅ | .env |
| Intake #TASK | ✅ | `app/bot/handlers.py` |
| Кнопки Approve / Rework / Clarify / Full report | ✅ | callbacks `a:`, `r:`, `c:`, `f:` |
| Кнопка I merged | ✅ | callback `m:` |
| Паритет gate с API по roundtable | ✅ | `needs_approval` = critical_execute **или** `owner_approval_needed` в risk_table |

**Итог:** Рабочий канал intake + owner actions.

---

## 2. Dashboard (веб, HTML)

| Требование | Статус | Примечание |
|------------|--------|------------|
| OWNER_API_KEY | ✅ | X-API-Key / query `api_key` |
| `/tasks`, `/tasks/{id}` | ✅ | Jinja |
| **Действия владельца** | ✅ | `task_detail.html`: POST `/tasks/{id}/approve`, `rework`, `clarify`, `merged` → `apply_owner_decision` |
| Office game UI | ✅ | `office.html` + `game.js` → REST `/api/tasks/...` |

**Итог:** Просмотр и owner actions через формы и Office, не только Telegram.

---

## 3. Control API (`/api/...`)

| Endpoint | Метод | MCP tool |
|----------|-------|----------|
| /api/tasks | GET | `tasks_list` |
| /api/tasks | POST | `task_create` |
| /api/tasks/{id} | GET | `task_get` |
| /api/tasks/{id} | PATCH | `task_update` |
| /api/tasks/{id}/approve | POST | `task_approve` |
| /api/tasks/{id}/rework | POST | `task_rework` |
| /api/tasks/{id}/clarify | POST | `task_clarify` |
| /api/tasks/{id}/merged | POST | `task_mark_merged` |
| /api/tasks/{id}/pipeline/run | POST | `pipeline_run` |
| /api/tasks/{id}/runs | GET | `runs_list` |
| /api/tasks/{id}/execution-events | GET | `execution_events_list` |
| /api/tasks/{id}/logs | GET | `logs_get` |
| /api/system/health | GET | `health` (через api_client.health) |

**Итог:** Owner decisions и observability идут через явные POST/GET, не через PATCH status «в обход».

---

## 4. MCP (Cursor)

Инструменты зарегистрированы в `app/mcp_server/tools.py`, исполнение — `app/mcp_server/executor.py` → `app/shared/api_client.py`.

Подробная таблица: [docs/MCP.md](MCP.md).

**Требования env:** `MYWAVE_BASE_URL` (или `DASHBOARD_URL`), `OWNER_API_KEY`.

---

## Обязательные .env по способу

| Переменная | Telegram | Dashboard | API | MCP |
|------------|----------|-----------|-----|-----|
| OWNER_API_KEY | — | ✅ | ✅ | ✅ |
| TELEGRAM_BOT_TOKEN | ✅ | — | — | — |
| OWNER_CHAT_ID | ✅ | — | — | — |
| DATABASE_URL | ✅ | ✅ | ✅ | — (сервер) |
| MYWAVE_BASE_URL | — | — | — | ✅ |

---

## Известные ограничения (не баг канала)

- **pr_create** в MCP: по-прежнему сценарий «runner создал PR локально → `task_update(pr_url)`», не GitHub API из MCP.
- **Синхронная оркестрация:** единая реализация в `app/orchestrator/sync_run.run_sync_orchestration`; API вызывает через `run_task_orchestration`, Telegram — из `bot/handlers._run_orchestration` (см. ADR-005).
