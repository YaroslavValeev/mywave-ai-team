# Signal → Rationale → Suggestion → Action Relation (Phase 11.1)

## Путь

```
signal (raw data)
    ↓
rationale (why — Phase 11.0)
    ↓
action suggestion (what to do — Phase 11.1)
    ↓
safe action (if available — action_center)
    ↓
decision support (options, preferred, risk)
```

## Мост 11.0 → 11.1

- **Rationale** — объясняет «почему система так считает».
- **Action suggestion** — предлагает «что сделать», опираясь на rationale.
- **Safe action** — если в action_center есть подходящее действие (open_decision_queue, refresh_status и т.п.), suggestion может ссылаться на него через `safe_action_available`.
- **Decision support** — объединяет несколько suggestions в блок «что лучше сделать первым», с options и risk_if_ignored.

## Связь

- Suggestion **не** заменяет rationale — дополняет его.
- Suggestion **не** равен execution — указывает на recommended_next_step.
- Safe action — опциональная ссылка; если есть — owner может выполнить через /do <action>.
