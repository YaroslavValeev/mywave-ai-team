# Domain prompt profile model (Phase 10.2)

Объект step-specific domain prompt profile, передаваемый в workflow step.

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `workflow_step` | string | `pipeline` \| `roundtable` \| `court` \| `review` \| `summary` |
| `prompt_profile_key` | string | Идентификатор профиля (например `pipeline_execution`, `roundtable_viewpoints`, `court_judgement`) |
| `primary_domain` | string | Effective primary domain |
| `secondary_domains` | list[string] | До 2 secondary |
| `context_profile_type` | string | `execution` \| `viewpoints` \| `judgement` \| `summary` |
| `compact_context` | string | Текст контекста для подстановки в prompt (ограничен по длине) |
| `step_specific_focus` | string | Краткое описание фокуса шага (для explainability) |
| `included_sections` | list[string] | Секции context pack, включённые в профиль (summary, strengths, typical_tasks, methods, …) |
| `excluded_sections` | list[string] | Секции, явно опущенные для этого шага |
| `selection_reason` | string | Почему выбран такой профиль/домен (override или auto) |

## Workflow steps (минимальный набор)

- **pipeline** — акцент на task execution, methods, tools.
- **roundtable** — акцент на viewpoints, trade-offs, collaboration.
- **court** — акцент на judgement, decision rationale, risk framing.
- При необходимости: **review**, **summary** (можно добавить позже).

## Идея

Один effective domain context даёт разные «срезы» для разных шагов: контекст становится точнее по шагу, а не просто один и тот же compact_context везде.
