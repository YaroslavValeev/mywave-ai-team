# Collaboration model baseline (Phase 10.9)

## Поля handoff signal

- **source_role** — роль, которая «держит» или завершила работу (executor, reviewer, operator).
- **target_role** — роль, которой нужно передать (owner, reviewer, executor, operator).
- **handoff_type** — owner_to_reviewer | reviewer_to_executor | executor_to_reviewer | executor_to_owner | owner_to_executor | operator_to_owner | reviewer_to_owner и т.п.
- **handoff_reason** — причина handoff (pending approval, rework, long-running, degraded, блокер).
- **handoff_readiness** — ready | blocked | partial (готовность к передаче).
- **handoff_blockers** — список причин блокировки (если blocked).
- **handoff_signal_source** — task_id | project_key | role_key; откуда пришёл сигнал.
- **recommended_next_role** — кого рекомендуется подключить следующим.
- **collaboration_priority** — high | medium | low.

## Примеры handoff_type

- **executor_to_owner** — задача в WAIT_OWNER; executor выполнил, ждёт решения owner.
- **owner_to_executor** — rework; owner вернул задачу executor-у.
- **operator_to_owner** — runtime degraded/blocker; operator должен эскалировать owner-у.
- **reviewer_to_owner** — reviewer подготовил, нужен owner decision (если роли разделены).
- **owner_to_reviewer** — owner делегировал на review (если применимо).
- **executor_to_reviewer** — результат готов к review (если применимо).

## Связь с task status

- WAIT_OWNER, APPROVED_WAIT_MERGE → handoff executor_to_owner, target=owner.
- REWORK → handoff owner_to_executor, target=executor.
- IN_PIPELINE/ROUNDTABLE/COURT + long-running → может потребоваться operator или owner.
- DEGRADED → operator_to_owner.
