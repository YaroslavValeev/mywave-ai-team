# COLLABORATION_EXECUTION_PERSISTENCE — Phase 11.4

- **Файл:** `app/data/collaboration_executions.json` (override: `COLLABORATION_EXECUTIONS_PATH`).
- **Структура:** `{ "executions": { "<execution_id>": { ... } } }`.
- **Связь с suggestions:** `suggestion_fingerprint` + `suggestion_snapshot`.
- **Статусы и closure:** поля `execution_status`, `closed_at`, `closure_reason`.
- **Audit:** отдельные события в `audit_events` через `log_audit` (не дублировать полный JSON execution в каждом событии — только ids и статусы).
