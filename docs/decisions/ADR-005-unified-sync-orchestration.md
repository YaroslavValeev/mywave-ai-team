# ADR-005: Единый синхронный цикл оркестрации (API + Telegram)

- Статус: Accepted
- Дата: 2026-04-08

## Контекст

До объединения логика `triage → pipeline → roundtable → court` дублировалась: в `app/dashboard/api_router.run_task_orchestration` и в `app/bot/handlers._run_orchestration`. Расхождения по audit (`pipeline_start`, `orchestration_done`), лимиту summary и вызову governance увеличивали риск регрессий и нарушали правило «один lifecycle engine».

## Решение

- Вся синхронная оркестрация живёт в `app/orchestrator/sync_run.py`, функция `run_sync_orchestration`.
- `run_task_orchestration` в API — тонкая обёртка: 404 при отсутствии задачи, иначе результат `run_sync_orchestration`.
- Telegram-бот вызывает тот же `run_sync_orchestration(..., source="telegram")` и только форматирует ответ пользователю.
- Лимит длины summary берётся из policy (`limits.telegram_summary_max_chars`), если не передан явный `summary_max_chars`.

## Последствия

- Monkeypatch тестов для stub шагов оркестрации должен целить `app.orchestrator.sync_run`, а не `api_router`.
- Фоновый runtime с `control=` по-прежнему идёт через `run_task_orchestration` → `run_sync_orchestration`.

## Откат

Вернуть тело `run_task_orchestration` и inline-цикл в handlers из истории git до этого ADR (два дублирующих блока).
