# Phase 10.1 — Acceptance

## Что считается завершённым

- [x] Workflow domain context model описана (WORKFLOW_DOMAIN_CONTEXT_MODEL, контракты).
- [x] Integration points описаны (DOMAIN_WORKFLOW_INTEGRATION_POINTS).
- [x] Workflow context service layer есть (`workflow_domain_context.py`, `domain_override_store.py`).
- [x] Owner override baseline есть (store, apply_domain_override, команда `/set_task_domain`).
- [x] Effective domain context живёт рядом с задачей (get_effective_domain_context, triage_result).
- [x] Workflow получает compact domain context (pipeline handoff, court report).
- [x] Owner видит override/effective domain (карточка задачи, `/task_domain`, dashboard task detail).
- [x] Audit работает (domain_triage, domain_override, domain_context_used).
- [x] Recommendation refinement есть (get_domain_aware_signals использует effective domain).
- [x] Playbook и relation docs есть (DOMAIN_WORKFLOW_PLAYBOOK, при необходимости DOMAIN_OVERRIDE_RELATION).
- [x] Тесты покрывают форму контекста, override precedence, persistence/audit, команды, интеграцию после triage, owner view, recommendations, регрессию Phase 9.9.

## Что остаётся следующим этапом

- Deeper agent-specific prompt selection.
- Richer override UX (например, выбор из списка в UI).
- Stronger project–domain mapping.
- Domain-aware role recommendations.
- Optional LLM explanation assist для domain selection.
