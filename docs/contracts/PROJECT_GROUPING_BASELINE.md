# Project grouping baseline (Phase 9.2)

Текущая модель проекта ещё не нормализована как отдельная сущность в owner-слое, поэтому используется практичный baseline grouping.

## Как определяется grouping
1. `task.domain` (если заполнен triage/pipeline);
2. иначе `task.task_type`;
3. иначе fallback `"general"`.

## Источники
- `TaskRepository` / таблица `tasks`.

## Ограничения
- Это не полноценная project hierarchy.
- Одна задача может логически относиться к нескольким проектам, но baseline даёт только одну группу.
- При улучшении project model baseline заменяется явной привязкой `task -> project`.
