# Phase 10.6 — Acceptance (Semi-manual registry refinement workflow)

## Что считается завершённым

- [x] ADR-040 зафиксирован (semi-manual workflow, принципы, non-goals).
- [x] Refinement proposal model описана (REFINEMENT_PROPOSAL_MODEL).
- [x] Refinement lifecycle описан (REFINEMENT_LIFECYCLE_MODEL).
- [x] Persistence baseline: REFINEMENT_PROPOSAL_PERSISTENCE, refinement_proposal_store.py (JSON).
- [x] Apply policy описана (REFINEMENT_APPLY_POLICY); apply = отметка + audit, экспорт candidate для ручного применения.
- [x] Audit model (REFINEMENT_AUDIT_MODEL); события created, reviewed, accepted, rejected, applied, change_exported.
- [x] Сервисы: refinement_proposals.py (generate, list, get, review, mark_applied), refinement_exports.py (export_proposal, export_pending, build_registry_patch_candidate).
- [x] Presenters: refinement_proposal_presenters.py (list, card, review_result, export, Telegram formatters).
- [x] Web: /owner/refinement/proposals, /owner/refinement/proposal/{id}; API: generate, list, get, review, apply, export; ссылки с /owner/refinement.
- [x] Telegram: /refinement_proposals [generate], /refinement_proposal <id>, /review_refinement <id> accept|reject [note].
- [x] Recommendations: get_pending_refinement_attention, pending_refinement_proposals в get_domain_aware_signals; refinement_review в get_next_actions при pending_count >= 1.
- [x] Playbooks: REFINEMENT_PROPOSAL_PLAYBOOK, REGISTRY_TUNING_PLAYBOOK; relation: ANALYTICS_TO_REFINEMENT_RELATION.
- [x] Тесты: generation, lifecycle, export, audit, routes, commands, presenters, recommendations, регрессия 10.5.

## Что остаётся следующим этапом

- Richer project-domain lifecycle.
- Collaboration flows.
- Explanation assist.
- Semi-automated registry tuning (безопасная запись в YAML по типам).
- Agent-specific tuning workflow.
