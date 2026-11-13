# Role–domain recommendation model (Phase 10.3)

Рекомендация «роли нужен фокус на домене» — объяснимая, с действием и доказательной базой.

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `role_key` | string | owner | operator | executor | reviewer |
| `recommended_domains` | list[string] | Домены, на которые роли стоит обратить внимание |
| `current_domain_pressure` | list[dict] | Давление по доменам: domain_key, count, reason |
| `domain_gap_signals` | list[dict] | Сигналы «не хватает внимания» по домену |
| `why_this_role_needs_it` | string | Краткое объяснение, зачем этой роли этот домен |
| `recommended_action` | string | Что сделать |
| `evidence_summary` | string | На чём основан вывод (например «3 задачи в legal ждут approve») |

## Роли (минимальный набор)

- **owner** — backlog, rework, override mismatches, cross-project приоритеты по доменам.
- **operator** — домены, где сконцентрированы degraded/stuck/blockers.
- **executor** — домены с наибольшей активной работой (active tasks, artifacts).
- **reviewer** — домены, где сконцентрированы pending approvals и decision queue.

Для каждой рекомендации: зачем этой роли нужен этот домен, что делать, на чём основан вывод (rule-based, explainable).
