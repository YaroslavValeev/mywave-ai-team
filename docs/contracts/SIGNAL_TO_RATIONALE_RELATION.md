# Signal → Rationale Relation (Phase 11.0)

## Путь

```
signal (raw data)
    ↓
evidence (2–5 фактов)
    ↓
rationale (headline, summary, reason)
    ↓
recommendation (что делать)
    ↓
action (конкретный следующий шаг)
```

## Примеры

1. **Domain**: domain_triage result → «Триаж: legal», «Override: нет» → «Домен legal по ключевым словам» → «Проверить override при необходимости» → /task_domain, /set_task_domain.

2. **Collaboration**: pending approvals → «3 задачи WAIT_OWNER» → «Handoff executor→owner — approval bottleneck» → «Разобрать approvals» → /approvals.

3. **Refinement**: refinement_backlog item → «Fallback в домене X» → «Proposal: расширить профиль» → «Принять/отклонить proposal» → /refinement_proposal.

## Связь

- **Signal** — источник данных (get_effective_domain_context, get_collaboration_hotspots и т.п.).
- **Evidence** — извлечённые факты (список строк).
- **Rationale** — человекочитаемое объяснение.
- **Recommendation** — suggested_action из сигнала или общий pattern.
- **Action** — команда или UI action.
