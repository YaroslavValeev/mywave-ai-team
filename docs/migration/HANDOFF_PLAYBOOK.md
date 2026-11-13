# HANDOFF_PLAYBOOK — Phase 10.9

## Назначение

Playbook описывает handoff-паттерны между ролями и когда они применяются.

## Типы handoff

| handoff_type           | source_role | target_role | Когда возникает                    |
|------------------------|-------------|-------------|------------------------------------|
| executor_to_owner      | executor    | owner       | Pending approval                   |
| owner_to_executor      | owner       | executor    | Rework                             |
| reviewer_to_owner      | reviewer    | owner       | Items need owner decision          |
| operator_to_owner      | operator    | owner       | Runtime degraded, escalation       |
| owner_to_operator      | owner       | operator    | (редко) Проверить runtime          |
| reviewer_to_executor   | reviewer    | executor    | (редко) Доработать по rework       |

## Handoff readiness

- **ready** — handoff может произойти, блокеров нет.
- **partial** — частично готово, возможны задержки.
- **blocked** — handoff заблокирован (например, owner не разбирает approvals).

## Handoff blockers

Примеры:
- «N задач ждут решения owner» — approval_bottleneck.
- Пустой список — handoff не заблокирован.

## Рекомендуемое поведение

1. **executor_to_owner (pending)** — owner разбирает approvals: approve / rework / clarify.
2. **owner_to_executor (rework)** — executor дорабатывает по фидбеку.
3. **operator_to_owner (degraded)** — owner проверяет Molt, логи, boundary.
4. **operator_to_owner (blockers)** — owner приоритизирует, снимает блокеры или откладывает.

## Источники данных

- `get_awaiting_decisions_summary` — pending approvals.
- `get_rework_signal_summary` — rework tasks.
- `get_blockers_summary`, `get_long_running_summary` — blockers, long-running.
- `get_system_status_summary` — degraded.
- `get_project_pending_approvals`, `get_project_risks` — project-level.

## Non-goals

- Не строить BPM/workflow engine.
- Не делать обязательный human routing.
- Не менять canonical task/run lifecycle.
- Handoff — advisory, не enforcement.
