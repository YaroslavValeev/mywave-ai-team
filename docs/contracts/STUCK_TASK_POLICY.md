# Stuck task policy (Phase 9.1)

Простая операционная эвристика для обнаружения «зависших» задач. Без ML и сложной эвристики.

---

## Определение

**Stuck task** — задача, которая слишком долго находится в одном из состояний:

- **waiting approval** — статус WAIT_OWNER или APPROVED_WAIT_MERGE дольше порога;
- **running without progress** — задача в статусе IN_PIPELINE / IN_ROUNDTABLE / IN_COURT без смены состояния и без обновления (updated_at) дольше порога;
- **degraded dependency** — опционально: задача в активном состоянии, но Molt degraded (можно не слать stuck по каждой задаче, а только degraded alert; в baseline достаточно первых двух).

В Phase 9.1 достаточно **одного порога по времени** для состояний «ожидание решения» и «без прогресса».

---

## Порог (документированный)

- **STUCK_WAITING_APPROVAL_MINUTES** — время в минутах, после которого задача в WAIT_OWNER или APPROVED_WAIT_MERGE считается stuck. **Default: 1440** (24 часа).
- **STUCK_NO_PROGRESS_MINUTES** — время в минутах без обновления (updated_at) для активных статусов IN_PIPELINE, IN_ROUNDTABLE, IN_COURT. **Default: 360** (6 часов).

Настраивается через env или config, например:

- `OWNER_NOTIFY_STUCK_WAITING_APPROVAL_MINUTES=1440`
- `OWNER_NOTIFY_STUCK_NO_PROGRESS_MINUTES=360`

---

## Критерий «stuck» для уведомления

1. Задача в WAIT_OWNER или APPROVED_WAIT_MERGE и `(now - updated_at) >= STUCK_WAITING_APPROVAL_MINUTES` → stuck «waiting approval».
2. Задача в IN_PIPELINE, IN_ROUNDTABLE или IN_COURT и `(now - updated_at) >= STUCK_NO_PROGRESS_MINUTES` → stuck «no progress».

Для каждой такой задачи отправляется не более одного stuck_task alert за **STUCK_ALERT_COOLDOWN_MINUTES** (default: 1440, т.е. раз в сутки на задачу).

---

## Source of truth

- Статус и updated_at — из TaskRepository (Task.updated_at, Task.status).
- Пороги — из owner notification config/env (см. OWNER_NOTIFICATION_SETTINGS.md и данный документ).
