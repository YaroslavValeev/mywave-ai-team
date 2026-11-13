# Domain override model (Phase 10.1)

Формализация owner override для primary domain задачи.

---

## Поля override записи

| Поле | Тип | Описание |
|------|-----|----------|
| **task_id** | int | Идентификатор задачи. |
| **previous_primary_domain** | string \| null | Primary до override (для аудита). |
| **new_primary_domain** | string | Новый primary (domain_key из registry). |
| **override_reason** | string \| null | Причина (произвольный текст). |
| **override_actor** | string | Кто задал (например owner_telegram, owner_web). |
| **override_source** | string | Источник команды. |
| **override_timestamp** | datetime/string | Когда установлен. |
| **override_active** | bool | Активен ли override (для возможного «сброса»). |

---

## Правила

- Override имеет приоритет над auto-selection при вычислении effective domain context.
- При отсутствии override effective context = результат select_context_for_task(task_text).
- Override сохраняется (файл или БД) и переживает перезапуск.
- Установка override логируется в audit (domain_override).
- Owner видит в карточке задачи: effective primary; «Override: yes» и причину, если override активен.
