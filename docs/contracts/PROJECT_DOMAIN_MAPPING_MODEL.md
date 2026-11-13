# Project–domain mapping model (Phase 10.3)

Объект project-domain profile: объяснимая сводка по доменам экспертизы в рамках проекта (project_key).

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `project_key` | string | Ключ проекта (группа задач: domain/task_type/general) |
| `dominant_domain` | string | Доминирующий домен экспертизы (effective primary по задачам проекта) |
| `secondary_domains` | list[string] | Следующие по весу домены (выше порога) |
| `domain_distribution` | dict[str, int] | Распределение: домен → количество задач |
| `domain_signal_source` | string | «tasks» — по активным/недавним задачам |
| `mapping_confidence` | string | «high» / «medium» / «low» — по количеству задач и ясности доминанты |
| `mismatch_signals` | list[dict] | Сигналы расхождения (override_heavy, correction_rate, …) |
| `updated_at` | string (ISO) | Момент вычисления (on read) |
| `task_count` | int | Число учтённых задач |
| `override_count` | int | Число задач с активным override в проекте |

## Explainability

- По каким задачам определён домен: активные и недавние задачи проекта; для каждой берётся effective_domain_context (override или auto).
- Почему домен primary: максимальная доля задач с этим effective primary_domain.
- Когда secondary важен: следующий домен с долей выше порога (например ≥2 задачи или ≥20%).
- Когда сигнал слабый: мало задач, размытый mix (mapping_confidence = low).
