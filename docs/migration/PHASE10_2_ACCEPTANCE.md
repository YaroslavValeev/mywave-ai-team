# Phase 10.2 — Acceptance

## Что считается завершённым

- [x] Step-specific prompt profile model описана (DOMAIN_PROMPT_PROFILE_MODEL, DOMAIN_STEP_CONTEXT_POLICY).
- [x] Context policy описана (какие секции для pipeline/roundtable/court, лимиты длины).
- [x] Prompt service layer есть (domain_prompt_profiles.py: build_pipeline/roundtable/court_domain_prompt, build_domain_prompt_for_step).
- [x] Workflow использует step-specific domain prompts (pipeline, roundtable, court интегрированы).
- [x] Richer override UX: /task_domain с подсказками, /clear_task_domain; web: список доменов, apply/clear override в task detail.
- [x] Clear override: service (clear_override), Telegram /clear_task_domain, web кнопка и POST /clear-domain; audit domain_override_cleared.
- [x] Debug endpoint: GET /api/tasks/{id}/domain-context (effective context, step profiles, override status, explainability).
- [x] Owner visibility: task detail — effective domain, override, step hint (pipeline/court focus), override controls.
- [x] Recommendation refinement: override_signals (override_mismatch_signal, manual_domain_correction_signal) в get_domain_aware_signals.
- [x] Playbook и relation docs (DOMAIN_OVERRIDE_AND_PROMPT_PLAYBOOK, DOMAIN_PROMPT_OVERRIDE_RELATION, DOMAIN_OVERRIDE_LIFECYCLE, DOMAIN_PROMPT_EXPLAINABILITY).
- [x] ADR-036 и acceptance doc.
- [x] Тесты покрывают профили по шагам, shape, override effect, clear, debug endpoint, owner view, recommendation signals, регрессию 10.1; при необходимости web override wiring.

## Что остаётся следующим этапом

- Deeper agent specialization.
- Richer project–domain mapping.
- Domain-aware role recommendations.
- Optional LLM-assisted explanation.
- Stronger override analytics.
