# Workflow domain context model (Phase 10.1)

Объект контекста, передаваемый в workflow и в prompt/context layer.

---

## Поля (минимальный набор)

| Поле | Тип | Описание |
|------|-----|----------|
| **selected_primary_domain** | string | Эффективный primary domain (с учётом override). |
| **selected_secondary_domains** | list[string] | Secondary domains (до 2). |
| **selected_context_pack_keys** | list[string] | Ключи доменов, чьи packs включены. |
| **compact_context** | string | Краткий текст контекста для промпта (ограничен по длине). |
| **context_selection_reason** | string | Почему выбран этот набор. |
| **context_selection_source** | string | `auto`, `override`, `fallback`. |
| **domain_override** | bool | Был ли применён owner override. |
| **domain_override_source** | string | Откуда override (например `owner_telegram`). |
| **domain_override_reason** | string | Причина override (если есть). |
| **domain_context_version** | string | Версия правил/модели. |

---

## Использование

- После triage вызывается **select_domain_context_for_workflow(task_text, task_id)**; при наличии override для task_id effective primary берётся из override.
- Объект кладётся в **triage_result["workflow_domain_context"]** и передаётся в pipeline, roundtable, court.
- **Pipeline/court** при формировании handoff/report могут включить **compact_context** (или его часть) в артефакт.
- **Owner** видит effective primary и флаг override в карточке задачи.
