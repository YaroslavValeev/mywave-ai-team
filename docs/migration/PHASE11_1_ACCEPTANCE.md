# PHASE11_1_ACCEPTANCE — Collaboration Action Suggestions and Decision Support Baseline

## Статус: accepted

## Что считается завершённым

- [x] **Action suggestion model** — описана в `docs/contracts/ACTION_SUGGESTION_MODEL.md`.
- [x] **Decision support model** — описана в `docs/contracts/DECISION_SUPPORT_MODEL.md`.
- [x] **Heuristics** — `docs/contracts/ACTION_SUGGESTION_HEURISTICS.md`.
- [x] **Service layer** — `app/services/collaboration_action_suggestions.py`: get_task_action_suggestions, get_project_action_suggestions, get_portfolio_action_suggestions, get_role_action_suggestions, get_collaboration_action_suggestions, get_decision_support.
- [x] **Presenters** — `app/presenters/action_suggestion_presenters.py`.
- [x] **Surfaces** — project (owner_project_detail), portfolio (owner_portfolio), role views (operator, executor, reviewer), decision-support page.
- [x] **Web/API** — /owner/decision-support, /api/owner/decision-support, /api/owner/action-suggestions.
- [x] **Telegram** — /suggestions, /project_suggestions, /role_suggestions, /decision_support.
- [x] **Action center linkage** — suggestions ссылаются на safe_action_available (open_decision_queue, recheck_molt_health); owner_recommendations включает suggested_safe_action.
- [x] **Playbooks** — COLLABORATION_ACTION_SUGGESTIONS_PLAYBOOK.md, DECISION_SUPPORT_PLAYBOOK.md.
- [x] **Relation docs** — SIGNAL_RATIONALE_SUGGESTION_ACTION_RELATION.md.
- [x] **Owner recommendations** — учитывают suggestions (suggested_safe_action).
- [x] **Tests** — test_phase11_1_action_suggestions.py.

## Definition of Done

- Action suggestion model описана.
- Decision support model описана.
- Heuristics описаны.
- Service layer есть.
- Presenters есть.
- Surfaces показывают suggestions.
- Web/API и Telegram entrypoints есть.
- Action center linkage есть.
- Playbooks и relation docs есть.
- Recommendations учитывают suggestions.
- Тесты проходят.
- ADR-045 и acceptance созданы.

## Что остаётся следующим этапом

- Richer semi-automated tuning.
- Agent-specific tuning workflows.
- Optional LLM explanation assist.
- Deeper decision support.
- Collaboration action execution patterns.
