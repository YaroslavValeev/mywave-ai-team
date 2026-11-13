# Collaboration effectiveness aggregates (Phase 11.5)

Агрегаты **read-only** поверх сохранённых outcomes + evaluate; не дублируют execution store.

## `execution_effectiveness_summary`
- **Purpose:** одна страница/блок для owner/GM: сколько effective / ineffective / follow-up.
- **Aggregation window:** параметр `window_days` (по `measured_at` / `baseline_captured_at` записей).
- **Evidence source:** `collaboration_outcomes.json`, записи с outcome в окне.
- **Output shape:** объект с полями `effective_executions_count`, `ineffective_executions_count`, `partially_effective_count`, `not_enough_signal_count`, `followup_needed_count`, `total_outcomes_in_window`, `explainable`, `evidence_source`, `effectiveness_by_execution_type`, `effectiveness_by_role_pair`, `effectiveness_by_project`.

## `effective_executions_count` / `ineffective_executions_count`
- **Purpose:** счётчики по `effectiveness_label`.
- **Window:** как у summary.
- **Evidence:** persisted outcomes после evaluate.
- **Output:** int.

## `followup_needed_count`
- **Purpose:** сколько outcomes с `followup_needed=true`.
- **Window:** как у summary.
- **Evidence:** persisted outcomes.
- **Output:** int.

## `effectiveness_by_execution_type`
- **Purpose:** разрез по `execution_type` → счётчики по label.
- **Window:** как у summary.
- **Evidence:** поле `execution_type` в outcome.
- **Output:** `dict[str, dict[str, int]]`.

## `effectiveness_by_role_pair`
- **Purpose:** разрез по упорядоченной паре ролей из `roles_involved` (или одна роль).
- **Window:** как у summary.
- **Evidence:** `roles_involved` в outcome.
- **Output:** `dict[str, dict[str, int]]`.

## `effectiveness_by_project`
- **Purpose:** только `subject_type=project`.
- **Window:** как у summary.
- **Evidence:** `subject_key` проекта.
- **Output:** `dict[project_key, dict[label, int]]`.

## `effectiveness_hotspots`
- **Purpose:** где чаще **ineffective** / **partially_effective** (пересмотр паттерна).
- **Window:** параметр.
- **Evidence:** агрегация по `(execution_type, subject_type, subject_key)` с примерами `outcome_reason`.
- **Output:** `{ items: [{ execution_type, subject_type, subject_key, count, sample_reasons[] }], ... }`.
