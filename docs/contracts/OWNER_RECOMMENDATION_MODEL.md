# Owner recommendation model (Phase 9.3)

## next_action

- **Purpose:** Один следующий шаг для owner.
- **Source of truth:** Агрегация из blockers, decision queue, rework, degraded, long-running.
- **Trigger/heuristic:** Правила из OWNER_RECOMMENDATION_HEURISTICS (приоритет: approvals → degraded → blockers → rework → long-running).
- **Output shape:** `{ "action_type", "task_id"?, "reason", "priority", "suggested_action", "if_deferred"? }`
- **Freshness:** On-demand.
- **Explainability:** reason и suggested_action обязательны.

## decision_queue_item

- **Purpose:** Элемент очереди решений с приоритетом и объяснением.
- **Source of truth:** Pending approvals, rework требующие owner, long-running, degraded-related.
- **Trigger:** Наличие задач в соответствующих категориях.
- **Output shape:** `{ "task_id", "reason", "priority", "suggested_next_action", "if_ignored"? }`
- **Freshness:** On-demand.
- **Explainability:** reason и suggested_next_action обязательны.

## strategic_digest

- **Purpose:** Недельная стратегическая сводка.
- **Source of truth:** owner_insights (weekly) + risk/priority signals + next_actions.
- **Output shape:** window_days, completed_count, key_risks[], what_moved[], what_stalled[], needs_decision[], next_week_priorities[], owner_focus.
- **Freshness:** 7 дней.
- **Explainability:** Каждый блок имеет явный источник (counts, lists, rules).

## project_health_signal

- **Purpose:** Статус группы (project baseline): healthy / attention_needed / critical.
- **Source of truth:** Группировка задач + счётчики (active, pending, rework, degraded, long-running).
- **Trigger:** Rule-based по порогам (см. heuristics).
- **Output shape:** `{ "project", "status", "reason", "active_count", "pending_count", ... }`
- **Freshness:** On-demand.
- **Explainability:** status выводится из правил по счётчикам.

## priority_signal

- **Purpose:** Сигнал «на что обратить внимание» с приоритетом.
- **Source of truth:** Тот же, что next_action / risk_signal; может дублировать для списка «приоритеты».
- **Output shape:** `{ "kind", "reason", "priority", "suggested_action" }`
- **Explainability:** reason обязателен.

## risk_signal

- **Purpose:** Риск с объяснением и предложенным действием.
- **Source of truth:** Degraded, накопленные rework, long-running, блокеры без движения.
- **Output shape:** `{ "risk_type", "reason", "why_it_matters", "suggested_action" }`
- **Explainability:** reason и why_it_matters обязательны.

## recommendation_reason

- **Purpose:** Текстовое объяснение рекомендации.
- **Format:** Короткая фраза на основе правил, например: «Pending approvals > 0», «Repeated rework по задаче N», «Degraded state».

## Monthly digest baseline

- **Purpose:** Сводка за последние 30 дней.
- **Source of truth:** Tasks, decisions, audit_events за 30 дней.
- **Output shape:** completed_count, active_count, pending_approvals_count, rework_count, degraded_incidents_count, top_blockers[], top_recommendations[].
- **Freshness:** 1 раз в месяц (scheduled) или on-demand.
- **Explainability:** Агрегаты с явными окнами и правилами.
