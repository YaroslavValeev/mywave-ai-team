# Collaboration outcome model (Phase 11.5)

Запись outcome **не** заменяет execution; это аналитический слепок эффекта интервенции.

## Идентификаторы
| Поле | Описание |
|------|-----------|
| `outcome_id` | Стабильный id: `co_{execution_id}` |
| `execution_id` | Связь с collaboration execution |
| `suggestion_id` | Из execution (если был) |

## Контекст субъекта
| Поле | Описание |
|------|-----------|
| `subject_type` | Напр. `project`, `portfolio` |
| `subject_key` | Ключ области |
| `roles_involved` | Роли из execution / snapshot |

## Сигналы
| Поле | Описание |
|------|-----------|
| `baseline_signal_state` | Человекочитаемая строка-сводка снимка при **close** |
| `baseline_signal_bundle` | JSON-снимок полей (`global_pending`, `global_rework`, …) |
| `post_execution_signal_state` | Сводка после **evaluate** |
| `post_execution_signal_bundle` | JSON-снимок при evaluate |
| `primary_metric` | Имя сравниваемой метрики (explainable) |
| `baseline_metric_value` / `post_metric_value` | Числа для сравнения (если применимо) |

## Результат
| Поле | Описание |
|------|-----------|
| `outcome_status` | `improved` \| `unchanged` \| `worse` \| `insufficient_data` \| `pending_measurement` |
| `effectiveness_label` | `effective` \| `partially_effective` \| `ineffective` \| `not_enough_signal` |
| `outcome_reason` | Короткое текстовое обоснование |
| `followup_needed` | bool |
| `window_days` | Окно, переданное в evaluate |
| `measured_at` | ISO timestamp последнего evaluate / обновления |

## Примеры `outcome_status`
- `improved` — целевая метрика снизилась (bottleneck ослаб).
- `unchanged` — метрика на том же уровне.
- `worse` — метрика выросла.
- `insufficient_data` — нет baseline, NaN по проекту, execution не закрыт, отмена, короткое окно.

## Примеры `effectiveness_label`
- `effective` — подтверждённое улучшение сигнала.
- `partially_effective` — нет улучшения, но не деградация (часто `unchanged`).
- `ineffective` — явная неэффективность (`worse` или накопленный риск паттерна в агрегатах).
- `not_enough_signal` — нельзя сделать вывод.

## Связь с audit
См. `COLLABORATION_OUTCOME_AUDIT_MODEL.md`.
