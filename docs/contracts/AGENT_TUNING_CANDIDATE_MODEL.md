# Agent Tuning Candidate Model (Phase 11.2)

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `tuning_candidate_id` | str | Уникальный id |
| `specialization_key` | str | Ключ специализации |
| `domain_key` | str | Домен |
| `workflow_step` | str | Шаг workflow (pipeline, roundtable, etc.) |
| `candidate_type` | str | Тип tuning (см. ниже) |
| `problem_pattern` | str | Описание проблемы |
| `evidence_summary` | list[str] | Факты |
| `recommended_tuning_change` | str | Рекомендуемое изменение |
| `expected_effect` | str | Ожидаемый эффект |
| `severity` | str | high, medium, low |
| `status` | str | pending_review, accepted, rejected, converted, verified |
| `source_signals` | list[str] | Откуда пришёл сигнал |
| `window_days` | int | Окно аналитики |
| `created_at` | str | ISO timestamp |
| `reviewed_at` | str \| null | Когда отревьюили |
| `proposal_id` | str \| null | Если конвертирован в proposal |
| `verification_outcome` | str \| null | improved, unchanged, worse, insufficient_data |
| `verification_at` | str \| null | Когда верифицировали |

## candidate_type примеры

- `expand_specialization_keywords`
- `adjust_execution_focus`
- `tighten_guardrails`
- `refine_expected_output_type`
- `review_fallback_strategy`
- `review_specialization_profile`
