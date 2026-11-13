# Adaptive Decision Support Model (Phase 12.0)

## Scope types

- **task** — task_id scope
- **project** — project_key scope
- **portfolio** — cross-project
- **cross_layer** — collaboration vs tuning alignment

## Decision support output shape

```yaml
top_problem: string           # главная проблема (≤120 символов)
top_action: string            # главное действие
safe_action_available: bool
safe_action_key: string | null # action_center key если доступен
manual_path_required: bool
do_now: intervention_item
do_next: intervention_item | null
defer_count: int
defer_summary: string         # кратко: что отложить
evidence_trail: list[str]     # компактный (≤5 items)
```

## Owner answer (10–20 сек)

Owner должен увидеть:
1. **Главная проблема** — top_problem
2. **Главное действие** — top_action + (safe_action_key или manual path)
3. **Что не трогать** — defer_summary
4. **Где owner** — manual_path_required items
5. **Где делегировать** — safe_action_key, role hint

## Compact card

- headline: string (≤80)
- reason: string (≤120)
- first_step: string
- second_step: string | null
- fallback: string | null
- safe_action_key: string | null
