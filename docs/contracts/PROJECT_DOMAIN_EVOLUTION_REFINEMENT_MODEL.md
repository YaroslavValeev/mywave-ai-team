# Project-domain Evolution Refinement Model (Phase 11.9)

## Refinement classification

Lifecycle state + эвристики → **refinement_class**:

| refinement_class | описание | intervention_needed |
|------------------|----------|---------------------|
| weak_signal | Мало задач, профиль не определён | нет |
| transitional | Временный переход (drift с малыми объёмами) | мониторинг |
| normal_evolution | Healthy diversification, стабильный multi/single | нет |
| attention_needed | Harmful drift, unstable mix, override_heavy | да |

## Owner answer

Краткий ответ для owner surface:

- **normal_evolution** — «Нормальная эволюция проекта»
- **review_recommended** — «Рекомендуется review»
- **refinement_or_tuning** — «Рассмотреть refinement/tuning»
- **owner_attention** — «Требуется внимание owner»

## Связь с lifecycle_state

| lifecycle_state | refinement_class (по умолчанию) |
|-----------------|--------------------------------|
| weak_signal | weak_signal |
| override_heavy | owner_attention |
| drifting | transitional или attention_needed (см. drift heuristics) |
| stable_multi_domain | normal_evolution или attention_needed (см. diversification heuristics) |
| unstable | owner_attention |
| stable_single_domain | normal_evolution |

## Attention item

Структура для list_project_domain_attention_items:

- project_key
- attention_reason: string
- refinement_class
- owner_answer
- intervention_preferred: refinement_review | tuning_review | owner_attention
- linked_to_refinement_backlog: bool
- evidence_summary: list (кратко)
