# ADR-038: Domain-aware agent specialization and execution lanes

## Контекст

После Phase 10.3 система использует domain-aware triage, step-specific domain prompts и project/role-level domain intelligence, но execution lane ещё недостаточно специализируется на уровне agent step: один и тот же домен может требовать разного execution profile для pipeline, roundtable и court.

## Решение

Вводится слой agent specialization:

- **Specialization profiles** — machine-readable реестр: specialization_key, domain_key, workflow_step, execution_focus, expected_output_type, guardrails, selection_keywords.
- **Step/domain-based selection** — выбор профиля по effective domain + workflow step; при отсутствии совпадения — fallback profile; всегда explainable.
- **Execution lane** — объект task_id + step + effective_domain + selected_specialization + execution_focus + expected_output_type + guardrails + selection_reason; прикладывается к pipeline/roundtable/court поверх domain prompt.
- **Audit** — события specialization_selected, specialization_fallback_used; payload с task_id, step, effective_domain, selected_specialization, reason, fallback_used.
- **Owner/debug visibility** — компактный hint в task card и task detail; debug endpoint /api/tasks/{id}/specialization-context; команда /task_specialization &lt;id&gt;.

## Границы

- Specialization layer = advisory execution profile; не меняет canonical task/run lifecycle.
- Не заменяет policy/permission logic.
- Не становится black-box orchestration engine.

## Non-goals

- Не строить full autonomous planner.
- Не вводить opaque agent scoring.
- Не делать десятки микропрофилей без необходимости.
- Не тянуть сырые know_proff тексты в execution prompt.
