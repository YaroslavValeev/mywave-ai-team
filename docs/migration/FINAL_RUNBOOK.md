# FINAL RUNBOOK (Phase 7+)

Дата: 2026-04-08

## 1) Scope

Этот runbook закрывает оставшиеся шаги без big-bang:

- окно deprecation для legacy-сущностей;
- prod-like smoke (Telegram + API + MCP);
- финальный go/no-go Owner.

## 2) Preconditions

- `pytest` зелёный в целевом коммите;
- миграции `003` и `004` применены;
- `OWNER_API_KEY`, Telegram bot token и owner chat настроены;
- MCP tools доступны (health/tasks/approve/rework/clarify/runs/events).

## 3) Prod-like smoke checklist

1. Создать задачу через Telegram (`#TASK ...`) и убедиться, что появился `task_id`.
2. Дождаться финализации оркестрации: `WAIT_OWNER` или `DONE`.
3. Если `WAIT_OWNER`, выполнить `approve` из Telegram и проверить переход:
   - `APPROVED_WAIT_MERGE` при наличии `pr_url`;
   - `DONE` без `pr_url`.
4. Проверить те же owner-actions через API:
   - `POST /api/tasks/{id}/approve`
   - `POST /api/tasks/{id}/rework`
   - `POST /api/tasks/{id}/clarify`
   - `POST /api/tasks/{id}/merged`
5. Проверить MCP parity:
   - `task_approve`, `task_rework`, `task_clarify`, `task_mark_merged`;
   - `runs_list`, `execution_events_list`.
6. Проверить audit trail:
   - `triage_done`, `pipeline_start`, `pipeline_done`, `roundtable_done`, `orchestration_done`;
   - owner events `OWNER_APPROVED|OWNER_REWORK|OWNER_CLARIFY|OWNER_MERGED`.

## 4) Deprecation window checklist

1. Зафиксировать deprecation tag/release.
2. Снять backup БД и экспорт audit proof.
3. Подтвердить, что внешние каналы не читают deprecated fields напрямую.
4. В течение окна deprecation собрать ошибки/метрики по API/MCP.
5. Только после окна — планировать DDL на удаление legacy-полей/таблиц.

## 5) Go/No-Go criteria

- Нет расхождений owner-actions между Telegram/API/MCP.
- `Run` и `ExecutionEvent` заполняются для новых прогонов.
- Нет дублирования синхронной оркестрации вне `app/orchestrator/sync_run.py`.
- Ошибок уровня blocker в smoke нет.
