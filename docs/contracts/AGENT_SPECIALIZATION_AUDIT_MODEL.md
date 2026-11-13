# Agent specialization audit model (Phase 10.4)

## События

- **specialization_selected** — при выборе профиля для шага (pipeline/roundtable/court). Payload: task_id, workflow_step, effective_domain, selected_specialization, reason, fallback_used (false), matched_signals (если есть).
- **specialization_fallback_used** — когда выбран fallback-профиль (general_*). Payload: task_id, workflow_step, effective_domain, selected_specialization (= general_*), reason (например "no domain match"), fallback_used: true.
- **workflow_step_specialization_used** — опционально, при фактическом использовании lane в шаге; можно объединить с specialization_selected при логировании в pipeline/roundtable/court.

## Минимальные поля payload

- task_id
- workflow_step
- effective_domain
- selected_specialization
- reason
- matched_signals (опционально, list или string)
- fallback_used (bool)

Используется существующий audit pattern (log_audit(repo, event_type, task_id=..., payload=...)).
