# Task-domain metadata model (Phase 10.0)

Advisory metadata по экспертизному домену для задачи. Не заменяет canonical task lifecycle и не является обязательной core-семантикой.

---

## Поля (минимальный набор)

| Поле | Тип | Описание |
|------|-----|----------|
| **primary_domain** | string (domain_key) | Основной рекомендуемый домен экспертизы из registry. |
| **secondary_domains** | list[string] | Дополнительные домены (до 2–3). |
| **domain_confidence** | str или float | Уровень уверенности: "high", "medium", "low" или 0–1. |
| **domain_reason** | string | Краткое объяснение выбора (для owner). |
| **matched_keywords** | list[string] | Ключевые слова, по которым подобран домен. |
| **context_pack_keys** | list[string] | Ключи доменов, для которых выбран context pack (primary + optional secondary). |
| **domain_routing_version** | string | Версия/идентификатор правил routing (для воспроизводимости). |
| **domain_selection_source** | string | Источник: `triage`, `manual`, `fallback`, `owner_override`. |

---

## Связь с Task

- Существующее поле **Task.domain** = routing domain (PRODUCT_DEV, MEDIA_OPS и т.д.) — не меняется.
- **Expertise domain metadata** хранится отдельно: в JSON на задаче (domain_metadata_json), в auxiliary store или вычисляется on read из owner_text.
- Metadata не влияет на статус, approval, run; используется для контекста, подсказок и рекомендаций.

---

## Использование

- **Triage:** после разбора задачи заполняются primary_domain, secondary_domains, reason, matched_keywords.
- **Context selection:** context_pack_keys определяет, какие packs подставлять в промпты/рекомендации.
- **Owner views:** показываются primary_domain, domain_reason (compact), без перегрузки UI.
