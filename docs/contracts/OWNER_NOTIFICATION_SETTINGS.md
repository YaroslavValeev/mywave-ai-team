# Owner notification settings baseline (Phase 9.1)

Минимальный набор настроек без полноценной per-user preference model. Реализуется через **config/env/default**.

---

## Параметры

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `daily_summary_enabled` | bool | true | Включить ежедневную сводку. |
| `daily_summary_time` | time / string | "09:00" | Время отправки daily summary (локальное или UTC по реализации). |
| `weekly_digest_enabled` | bool | true | Включить weekly management digest. |
| `weekly_digest_day` | int | 1 | День недели ISO (1=понедельник). |
| `weekly_digest_time` | time / string | "09:10" | Время отправки weekly digest. |
| `approval_alerts_enabled` | bool | true | Уведомления о запросе approve (при переходе в WAIT_OWNER; основной месседж из handler). |
| `completion_alerts_enabled` | bool | true | Уведомления о завершении задачи / готовности артефакта. |
| `degraded_alerts_enabled` | bool | true | Уведомления о переходе в DEGRADED. |
| `recovery_alerts_enabled` | bool | true | Уведомления о восстановлении (DEGRADED → OK). |
| `stuck_task_alerts_enabled` | bool | true | Уведомления о «зависших» задачах по STUCK_TASK_POLICY. |

---

## Реализация

- Чтение: из конфига (например `app/config/owner_notifications.yaml`) или переменных окружения (префикс `OWNER_NOTIFY_`), иначе default.
- Пример env: `OWNER_NOTIFY_DAILY_SUMMARY_ENABLED=1`, `OWNER_NOTIFY_DAILY_SUMMARY_TIME=09:00`, `OWNER_NOTIFY_WEEKLY_DIGEST_ENABLED=1`, `OWNER_NOTIFY_WEEKLY_DIGEST_DAY=1`, `OWNER_NOTIFY_WEEKLY_DIGEST_TIME=09:10`.
- Не требуется отдельная таблица или API для смены настроек на первом этапе; при необходимости позже можно вынести в shared-core или dashboard.
