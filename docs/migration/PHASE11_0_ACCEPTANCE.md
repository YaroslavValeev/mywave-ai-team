# PHASE11_0_ACCEPTANCE — Explanation Assist and Rationale Surfaces

## Статус: accepted

## Что считается завершённым

- [x] **Rationale model** — описана в `docs/contracts/RATIONALE_MODEL.md`.
- [x] **Explanation service layer** — `app/services/explanation_assist.py` с функциями: `explain_task`, `explain_project`, `explain_portfolio`, `explain_role_view`, `explain_collaboration`, `explain_refinement`, `explain_signal`.
- [x] **Presenters** — `app/presenters/explanation_presenters.py`: `present_rationale_card`, `present_rationale_list`, `present_task_explanation`, `present_project_explanation`, `present_portfolio_explanation`, `present_collaboration_explanation`, `present_refinement_explanation`, Telegram formatters.
- [x] **Task/project/portfolio/collaboration/refinement surfaces** — блок «Почему система так считает» в task detail, owner project detail, owner portfolio, owner collaboration, owner refinement, owner refinement proposal detail.
- [x] **Debug/API layer** — `/api/explain/task/{id}`, `/api/explain/project/{key}`, `/api/explain/portfolio`, `/api/explain/collaboration`, `/api/explain/refinement`, `/api/explain/refinement/{proposal_id}`.
- [x] **Telegram explanation commands** — `/explain_task`, `/explain_project`, `/explain_portfolio`, `/explain_refinement`, `/explain_collaboration`.
- [x] **Recommendations linkage** — `owner_recommendations` поддерживает `rationale_headline` и `evidence_summary` для collaboration hotspot items.
- [x] **Playbooks** — `EXPLANATION_ASSIST_PLAYBOOK.md`, `RATIONALE_SURFACES_PLAYBOOK.md`.
- [x] **Relation docs** — `SIGNAL_TO_RATIONALE_RELATION.md` (существует).
- [x] **Tests** — `tests/test_phase11_0_explanation_assist.py` покрывает rationale shape, presenters, routes, recommendations, regression.

## Definition of Done

- Rationale model описана.
- Service layer есть.
- Presenters есть.
- Ключевые surfaces получили explanations.
- Debug/API и Telegram entrypoints есть.
- Recommendations умеют ссылаться на rationale.
- Playbooks и relation docs есть.
- Тесты проходят.
- ADR-044 и acceptance docs созданы/обновлены.

## Что остаётся следующим этапом

- Richer semi-automated tuning.
- Collaboration action suggestions.
- Agent-specific tuning workflows.
- Optional LLM-assisted explanation layer.
- Deeper decision support.
