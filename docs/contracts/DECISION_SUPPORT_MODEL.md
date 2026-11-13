# Decision Support Model (Phase 11.1)

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `decision_support_id` | str | Уникальный идентификатор |
| `decision_type` | str | approval_pending, project_intervention, portfolio_priority, collaboration_bottleneck, refinement_review |
| `scope_type` | str | task, project, portfolio, collaboration_hotspot, refinement_proposal_cluster |
| `scope_key` | str | ID/ключ области (task_id, project_key, null для portfolio) |
| `headline` | str | Краткий заголовок решения |
| `why_now` | str | Почему важно решить сейчас |
| `options` | list[dict] | Варианты: {label, description, action_hint} |
| `preferred_option` | str | Рекомендуемый вариант (label) |
| `preferred_option_reason` | str | Почему рекомендован |
| `risk_if_ignored` | str | Что будет, если игнорировать |
| `evidence_items` | list[str] | Факты |
| `related_suggestions` | list[str] | suggestion_id или ссылки на action suggestions |

## Scope examples

- **task** — scope_key = task_id
- **project** — scope_key = project_key
- **portfolio** — scope_type = portfolio, scope_key может быть null
- **collaboration hotspot** — scope_key = project_key или hotspot_type
- **refinement proposal cluster** — scope_key = null или proposal_ids
