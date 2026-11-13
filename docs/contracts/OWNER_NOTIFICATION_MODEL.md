# Owner notification model (Phase 9.1)

Формализация типов уведомлений, триггеров, payload и правил доставки.

---

## Типы уведомлений

| Type | Trigger | Payload (minimal) | Priority | Dedupe / Cooldown | Channel | Source of truth |
|------|---------|-------------------|----------|-------------------|---------|-----------------|
| `daily_summary` | Scheduled time | counts, state, top tasks/approvals | normal | Once per day (by configured time) | Telegram | owner_queries, get_system_status_summary |
| `weekly_digest` | Scheduled weekly time | managerial insight blocks | normal | Once per week | Telegram | owner_insights.get_weekly_digest |
| `approval_requested` | Task → WAIT_OWNER | task_id, summary snippet | high | Per task: не дублировать сразу после перехода (основное сообщение уже из handler) | Telegram | TaskRepository, canonical state |
| `task_completed` | Task → DONE | task_id, summary, report_path | normal | Per task: один раз при переходе | Telegram | TaskRepository |
| `artifact_ready` | Artifact/report ready for task | task_id, report_path, title | normal | Может объединяться с task_completed | Telegram | TaskRepository |
| `degraded_mode` | Health check: OK → DEGRADED | reason (e.g. molt down) | high | Один раз до перехода в recovered; cooldown (e.g. не чаще 1 раз в N минут) | Telegram | owner_queries._molt_health_check, get_system_status_summary |
| `recovered_mode` | Health check: DEGRADED → OK | — | normal | Один раз после последнего degraded alert | Telegram | owner_queries, get_system_status_summary |
| `stuck_task` | Periodic check: task in waiting/stale state > threshold | task_id, status, threshold | normal | Per task: cooldown (e.g. не чаще 1 раз в 24h на задачу) | Telegram | TaskRepository, STUCK_TASK_POLICY |

---

## Trigger

- **daily_summary:** cron-like / fixed time (e.g. 09:00), проверка при каждом проходе scheduler loop.
- **approval_requested:** событие в pipeline (handler уже шлёт сообщение; тип используется для консистентности и напоминаний в stuck).
- **task_completed / artifact_ready:** событие при обновлении задачи (DONE, report_path).
- **degraded_mode / recovered_mode:** периодический health check (тот же источник, что /status); сравнение предыдущего и текущего state.
- **stuck_task:** периодическая проверка списка задач по STUCK_TASK_POLICY (время в статусе / без прогресса).

---

## Payload

- **daily_summary:** `{ active_tasks_count, pending_approvals_count, state, molt_ok, top_tasks?, pending_approvals_list? }` — см. build_detailed_summary / build_short_summary.
- **approval_requested:** `{ task_id, summary? }`.
- **task_completed:** `{ task_id, summary?, report_path? }`.
- **artifact_ready:** `{ task_id, report_path, title? }`.
- **degraded_mode:** `{ reason?, molt_message? }`.
- **recovered_mode:** `{}`.
- **stuck_task:** `{ task_id, status, threshold_minutes? }`.

---

## Delivery

- Единственный канал в Phase 9.1: **Telegram** (send_owner_message).
- Форматирование — в presenter layer; решение о отправке — в service + notification_state (cooldown/dedupe).
