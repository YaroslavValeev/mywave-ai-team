# Phase 7 — Cleanup (репозиторий)

Дата прохода: 2026-04-08

## Что сделано в этом проходе

1. **MCP executor** — единый `import json`, helper `_json_pretty`, убраны повторяющиеся локальные `import json` в ветках tools.
2. **Документация** — `docs/USAGE_AUDIT.md` переписан под фактическое состояние (Dashboard owner actions, MCP tools, API approve/rework/clarify/runs/execution-events).
3. **Согласованность** — `docs/MCP.md` уже содержит расширенный список tools (см. Phase 6).
4. **Поздний проход (2026-04-08)** — `app/orchestrator/sync_run.py`: единый цикл для API и Telegram; ADR-005; обновлены `MERGE_PLAN`, `USAGE_AUDIT`, критерии ниже.
5. **Runbook** — добавлен `docs/migration/FINAL_RUNBOOK.md` (ручной prod-like smoke + deprecation window checklist + go/no-go).

## Что намеренно не трогали (без big-bang)

- ~~Слияние дублирующей оркестрации~~ — **выполнено** (2026-04-08): `app/orchestrator/sync_run.py`, ADR-005.
- Удаление legacy таблиц/полей до окна deprecation и миграции данных у Owner.

## Rollback

- Откат только к коммиту до Phase 7 для docs/executor; API контракты не менялись.

## Критерий «Phase 7 закрыта для этого репо»

- Нет заведомо ложной документации по каналам (audit usage).
- MCP executor без дублирования импортов в ветках.
- Синхронная оркестрация не дублируется (один модуль `sync_run`, см. ADR-005).
- `pytest` зелёный.
