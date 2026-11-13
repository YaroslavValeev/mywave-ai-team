# Action Suggestion Model (Phase 11.1)

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `suggestion_id` | str | Уникальный идентификатор (UUID или composite key) |
| `suggestion_type` | str | Тип suggestion (см. ниже) |
| `subject_type` | str | task, project, portfolio, collaboration_hotspot, role |
| `subject_key` | str | ID задачи, ключ проекта, role_key и т.п. |
| `source_role` | str | Роль, от которой ожидается handoff |
| `target_role` | str | Роль, которой рекомендовано действие |
| `headline` | str | Краткий заголовок |
| `reason` | str | Почему нужно действовать |
| `evidence_summary` | list[str] | 2–5 коротких фактов |
| `recommended_next_step` | str | Конкретный рекомендуемый шаг |
| `urgency` | str | high, medium, low |
| `confidence_label` | str | high, medium, low |
| `safe_action_available` | str \| null | Имя safe action, если есть (например `open_decision_queue`) |
| `related_objects` | list[dict] | task_id, project_key и т.п. |

## suggestion_type примеры

- `review_request` — запрос ревью
- `owner_attention_request` — требуется внимание owner
- `runtime_escalation` — эскалация operator → owner
- `handoff_followup` — закрыть handoff
- `approval_resolution_needed` — принять решение по approval
- `rework_loop_break` — разорвать rework loop (owner+executor)
- `project_focus_intervention` — вмешаться в проект (drift, instability)

## Связь с rationale

Suggestion строится на основе rationale (Phase 11.0). Rationale отвечает «почему», suggestion — «что делать».
