# Domain context persistence baseline (Phase 10.1)

Что хранится постоянно, что считается on read, как override влияет на effective context.

---

## Что хранится persistently

- **Override:** для каждой задачи с override — task_id, new_primary_domain, reason, actor, source, timestamp. Реализация: файл app/data/domain_overrides.json (или отдельная таблица при наличии миграции). Чтение при get_effective_domain_context(task_id, ...).

---

## Что считается on read

- **Auto-selection:** primary/secondary, compact_context, reason считаются из task_text через domain_triage/select_context_for_task при каждом запросе, если нет override или при сборке effective context поверх override.
- **Effective context:** при запросе effective context для task_id: 1) проверить override store; 2) если есть активный override — primary = override.new_primary_domain, compact_context = build по этому одному домену; 3) иначе — select_domain_context_for_workflow(task_text).

---

## Как TaskRepository / auxiliary store читает

- TaskRepository не обязан хранить domain context; workflow_domain_context строится сервисом workflow_domain_context.py и передаётся в triage_result.
- Override хранится в domain_override_store (файл или отдельный слой); get_effective_domain_context обращается к нему по task_id.

---

## Сводка

- **Persist:** только override (task_id → primary_domain, reason, actor, timestamp).
- **On read:** auto domain selection, compact_context, effective context (с учётом override).
