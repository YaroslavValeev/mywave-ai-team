# Phase 10.4 — Acceptance (Domain-aware agent specialization and execution lanes)

## Что считается завершённым

- [x] Specialization model описана (AGENT_SPECIALIZATION_MODEL, ADR-038).
- [x] Machine-readable registry: `app/data/agent_specializations/specializations.yaml` (legal, programming_engineer, finance, general; pipeline/roundtable/court).
- [x] Selection policy описана (AGENT_SPECIALIZATION_SELECTION_POLICY).
- [x] Specialization service layer: `app/services/agent_specializations.py` (list_specializations, get_specialization, suggest_specialization, get_default_specialization_for_domain, explain_specialization_choice, build_execution_lane).
- [x] Execution lane model (EXECUTION_LANE_MODEL) и передача в pipeline/roundtable/court.
- [x] Workflow использует specialization: pipeline/roundtable/court получают execution lane, блок Execution profile в handoff/report, аудит specialization_selected / specialization_fallback_used.
- [x] Audit: события specialization_selected, specialization_fallback_used с payload (workflow_step, effective_domain, selected_specialization, reason, fallback_used).
- [x] Owner/debug visibility: карточка задачи (профиль pipeline + fallback), `/task_specialization <id>`, GET `/api/tasks/{id}/specialization-context`.
- [x] Recommendation refinement: get_specialization_signals (specialization_fallback_hotspot, specialization_mismatch_signal, weak_execution_lane_signal), интеграция в get_domain_aware_signals.
- [x] Playbook и relation docs: AGENT_SPECIALIZATION_PLAYBOOK, DOMAIN_STEP_SPECIALIZATION_RELATION.
- [x] ADR-038 и acceptance doc.
- [x] Тесты: registry, suggest_specialization, step diversity, workflow attachment, debug endpoint, owner view, recommendations, регрессия Phase 10.2, Telegram command.

## Что остаётся следующим этапом

- Deeper project-domain lifecycle.
- Richer override analytics.
- Domain-aware collaboration flows.
- Optional explanation assist.
- Selective specialization tuning (расширение реестра по данным fallback/mismatch).
