# Owner recommendation heuristics (Phase 9.3)

Все правила rule-based и объяснимые.

## Next actions (приоритет порядка)

1. **Approvals pending** — если есть задачи в WAIT_OWNER/APPROVED_WAIT_MERGE → рекомендация «разобрать approvals» (список task_id); приоритет высокий.
2. **Degraded now** — если state == DEGRADED → рекомендация «проверить runtime / boundary»; приоритет высокий.
3. **Blockers** — long-running waiting_owner / running_without_progress → «снять блокер / пересмотреть приоритет» по task_id; приоритет средний.
4. **Repeated rework** — rework_cycles >= 2 или статус REWORK → «owner review / уточнение постановки» по task_id; приоритет средний.
5. **Stalled work** — long-running без прогресса → «пересмотреть приоритеты или завершить/отложить»; приоритет средний.

Лимит: 3–5 next actions.

## Decision queue (приоритизация)

- Элементы: (1) pending approvals (по давности — старые выше), (2) repeated rework с owner intervention, (3) long-running в waiting_owner, (4) degraded-related (если есть задача, связанная с инцидентом).
- Для каждого: reason (откуда взялось), priority (high/medium), suggested_next_action, if_ignored (кратко: «решения будут копиться», «задача останется в rework» и т.д.).

## Project health (по группе)

- **healthy:** pending_count == 0, нет long-running в группе, нет rework >= 2 в группе, нет degraded по группе (или глобально OK).
- **attention_needed:** pending_count >= 1 или long-running >= 1 или rework signals >= 1; при этом не critical.
- **critical:** pending_count >= 2 или (degraded_now и группа затронута) или много rework/long-running в группе (порог: например 2+ rework или 2+ long-running в одной группе).

Группа = project key (domain / task_type / general) из PROJECT_GROUPING_BASELINE.

## Risk signals

- **degraded_frequency** — если degraded_events_count_7d > 0 или current_state == DEGRADED → risk «операционная нестабильность»; why: «runtime/ boundary требуют проверки»; action: «проверить Molt / логи».
- **rework_accumulation** — если rework_count (за неделю/месяц) выше порога (например >= 2) → risk «накопление rework»; why: «качество постановки или исполнения»; action: «разбор тренда и приоритетов».
- **long_running_accumulation** — если long_running count > 0 → risk «задачи без прогресса»; why: «блокируют обзор»; action: «решить или отложить».
- **approvals_backlog** — если pending_approvals_count >= 2 → risk «очередь решений»; why: «замедляет поток»; action: «разобрать approvals».

## Strategic weekly digest

- Собирается из: completed_count, pending_approvals_count, blockers_count, rework_count, degraded_events_count за 7 дней.
- key_risks: список risk_signal за неделю (до 5).
- what_moved: top_completed (до 3).
- what_stalled: top_blockers / long-running (до 3).
- needs_decision: decision_queue до 5.
- next_week_priorities: первые 3 next_actions или owner_focus текст.
- owner_focus: один предложение (уже есть в weekly digest).

## Monthly digest (last 30 days)

- completed_count, active_count, pending_approvals_count, rework_count (за 30 дней), degraded_incidents_count (audit events за 30 дней).
- top_blockers: до 5 (из текущего snapshot блокеров).
- top_recommendations: до 3 next_actions или risk_signal.
- Окно: строго last 30 days; в документации зафиксировано.

## Пороги (конфигурируемые по умолчанию)

- Approvals «много»: >= 2.
- Rework «часто»: >= 2 за период.
- Long-running «много»: >= 1 (уже считается в insights).
- Project critical: pending >= 2 в группе или (degraded + группа с активными задачами) или rework в группе >= 2.
