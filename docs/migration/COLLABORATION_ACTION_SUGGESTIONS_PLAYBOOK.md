# COLLABORATION_ACTION_SUGGESTIONS_PLAYBOOK — Phase 11.1

## Назначение

Playbook описывает, как использовать collaboration action suggestions. Система не только объясняет сигналы (Phase 11.0), но и предлагает конкретные следующие шаги.

## Как читать suggestion cards

### Поля

- **headline** — краткий заголовок (что нужно сделать).
- **reason** — почему это нужно.
- **evidence_summary** — 2–5 фактов.
- **recommended_next_step** — конкретный рекомендуемый шаг.
- **urgency** — high, medium, low.
- **safe_action_available** — если есть — можно выполнить через /do &lt;action&gt;.

## Чем suggestion отличается от action

- **Suggestion** — рекомендация «что сделать». Owner/GM принимает решение.
- **Action** — исполняемая команда в action center (/do refresh_status и т.п.).
- Suggestion **не** выполняет автоматически. Suggestion может ссылаться на safe action (safe_action_available).

## Когда suggestion нужно выполнять сразу

- urgency = high и safe_action_available задан — можно /do &lt;action&gt;.
- approval_bottleneck — разобрать approvals.
- runtime_escalation — проверить Molt, recheck_molt_health.

## Когда сначала посмотреть rationale

- urgency = low.
- confidence_label = low.
- Нужно понять контекст — /explain_task, /explain_project.

## Как не путать recommendation, rationale и policy

- **Recommendation** (get_next_actions) — приоритизированный список «что сделать».
- **Rationale** (Phase 11.0) — «почему система так считает».
- **Action suggestion** — «что сделать» с recommended_next_step и optional safe_action.
- **Policy** — правила поведения системы (routing, approval). Не смешивать с suggestions.
