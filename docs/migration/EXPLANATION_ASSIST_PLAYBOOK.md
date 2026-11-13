# EXPLANATION_ASSIST_PLAYBOOK — Phase 11.0

## Назначение

Playbook описывает, как использовать explanation assist layer и rationale surfaces. Система генерирует множество explainable сигналов; explanation assist собирает их в единый слой «почему система так решила» и предоставляет компактные, понятные объяснения без инженерного мусора.

## Как читать explanation cards

### Short form (по умолчанию)

- **headline** — краткий заголовок, отвечающий на «почему».
- **evidence_items** — 2–5 коротких фактов, на основе которых построено объяснение.
- **recommended_action** — что рекомендовано сделать (если применимо).

Short form виден в task card, project detail, portfolio, collaboration, refinement views.

### Expanded form (debug / detail)

- Полный **rationale** с полями: reason, signals_used, confidence_label, related_objects.
- Используется в API `/api/explain/*` и debug-режиме.

## Где смотреть

| Surface           | Short form | Expanded | Команда / URL                                      |
|-------------------|-----------|----------|----------------------------------------------------|
| Task              | ✓         | API      | /tasks/{id}, /explain_task {id}                    |
| Project           | ✓         | API      | /owner/project/{key}, /explain_project {key}       |
| Portfolio         | ✓         | API      | /owner/portfolio, /explain_portfolio               |
| Collaboration     | ✓         | API      | /owner/collaboration, /explain_collaboration       |
| Refinement        | ✓         | API      | /owner/refinement, /explain_refinement [id]        |
| Debug API         | —         | ✓        | /api/explain/task/{id}, /api/explain/project/...   |

## Как owner/GM использовать rationale

1. **При принятии решения** — rationale показывает, какие сигналы привели к рекомендации. Если evidence_items убедительны — можно действовать. Если нет — нужен deeper manual analysis.
2. **При отладке** — когда поведение системы кажется неожиданным, использовать `/explain_task`, `/explain_project` и API endpoints для получения полного rationale.
3. **При настройке** — rationale помогает понять, что именно в domain/specialization/collaboration приводит к рекомендациям. Можно скорректировать routing, policy или конфигурацию.

## Как не путать explanation и policy

- **Explanation** — описание *почему* система выдала такое решение. Это наблюдательный слой, он не меняет логику.
- **Policy** — правила, *по которым* система принимает решения (routing, approval rules, critical flags). Policy — источник истины для логики; explanation — интерпретация результатов.

Explanation не подменяет policy. Если нужно изменить поведение — менять policy; explanation помогает понять текущее поведение.

## Когда explanation достаточно, а когда нужен deeper analysis

**Explanation достаточно**, когда:
- Нужно быстро понять, почему task/project в focus.
- Рекомендация очевидна, rationale подтверждает.
- Owner проверяет consistency (domain selection, override status).

**Нужен deeper analysis**, когда:
- confidence_label = low, evidence_items скудны.
- Рекомендация противоречит интуиции.
- Требуется разбор raw signals, audit trail, policy diff.
- Нужно изменить логику (тогда — policy, не explanation).

## Non-goals

- Не строить full conversational reasoning engine.
- Не зависеть от LLM как обязательного слоя (explanation — rule-based).
- Не выводить raw internal dumps в UI по умолчанию.
- Не смешивать explanation с policy/permission logic.
