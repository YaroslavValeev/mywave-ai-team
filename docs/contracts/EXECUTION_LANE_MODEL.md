# Execution lane model (Phase 10.4)

Объект, прикладываемый к шагу workflow: как именно выполнять шаг с учётом домена и выбранной специализации.

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `task_id` | int | Задача |
| `workflow_step` | string | pipeline \| roundtable \| court |
| `effective_domain` | string | Effective primary domain |
| `selected_specialization` | string | specialization_key выбранного профиля |
| `execution_focus` | string | Фокус исполнения из профиля |
| `expected_output_type` | string | Ожидаемый тип выхода |
| `guardrails` | list[string] | Ограничения |
| `selection_reason` | string | Почему выбран этот профиль |
| `fallback_used` | bool | Использован ли fallback |
| `profile_summary` | string | Краткое summary профиля (опционально) |

Используется при сборке prompt/context для pipeline, roundtable, court — поверх domain context (Phase 10.2). Не подменяет domain prompt, а дополняет его рамкой исполнения.
