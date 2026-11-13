# Action audit model (Phase 9.8)

Модель аудита выполнения действий через action center.

---

## Поля записи аудита

- **action_id** — уникальный идентификатор выполнения (uuid или id записи).
- **action_name** — имя действия (из registry).
- **role** — роль, от имени которой выполнено (owner, operator, executor, reviewer).
- **actor** — идентификатор актора (telegram_chat_id, api_key_id, "web").
- **context** — опциональный контекст (project_key, task_id, channel).
- **status** — success | failure | timeout.
- **started_at** — время начала (ISO).
- **finished_at** — время окончания (ISO).
- **result_summary** — краткое текстовое описание результата (для человека).
- **error_message** — при status=failure текст ошибки.

---

## Реализация

Используется существующая таблица **audit_events**:
- **event_type:** `action_center`
- **task_id:** null (или task_id при привязке к задаче в будущем).
- **payload_json:** объект с полями action_id, action_name, role, actor, context, status, started_at, finished_at, result_summary, error_message.

Так достигается единый audit trail без новой таблицы; запросы по action_center выполняются фильтром event_type = 'action_center'.
