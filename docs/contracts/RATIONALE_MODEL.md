# Rationale Model (Phase 11.0)

## Описание

Unified rationale — единый формат объяснения «почему система так решила». Используется во всех explanation surfaces.

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `rationale_id` | str | Уникальный идентификатор (опционально, для отладки) |
| `rationale_type` | str | Тип rationale (см. примеры ниже) |
| `subject_type` | str | task, project, portfolio, collaboration, refinement |
| `subject_key` | str | id задачи, project_key, proposal_id и т.п. |
| `headline` | str | Краткий заголовок (1–2 предложения) |
| `summary` | str | Расширенное описание (до 3 предложений) |
| `reason` | str | Основная причина |
| `evidence_items` | list[str] | 2–5 коротких фактов (максимум) |
| `signals_used` | list[str] | Типы сигналов, из которых собрано объяснение |
| `confidence_label` | str | high, medium, low |
| `recommended_action` | str | Что рекомендуется сделать (если уместно) |
| `related_objects` | list[dict] | Связанные сущности (task_id, project_key и т.п.) |
| `generated_at` | str | ISO timestamp |

## rationale_type

- `domain_selection_rationale`
- `specialization_rationale`
- `lifecycle_rationale`
- `collaboration_rationale`
- `refinement_rationale`
- `recommendation_rationale`

## Примеры

```json
{
  "rationale_type": "domain_selection_rationale",
  "subject_type": "task",
  "subject_key": "42",
  "headline": "Домен: legal — по ключевым словам и контексту задачи.",
  "summary": "Авто-выбор по триажу: в тексте преобладают термины договор, лицензия, согласование.",
  "evidence_items": ["Триаж: legal", "Override: нет", "Source: auto"],
  "signals_used": ["domain_triage", "workflow_domain_context"],
  "confidence_label": "high",
  "recommended_action": null
}
```
