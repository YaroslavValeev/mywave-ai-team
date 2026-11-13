# Specialization analytics model (Phase 10.5)

## Purpose

Агрегировать события выбора и fallback специализации из audit и дать explainable сводки и hotspots.

## Source of truth

- **audit_events**: `event_type` in (`specialization_selected`, `specialization_fallback_used`), `task_id`, `payload_json`, `created_at`.
- **payload**: `workflow_step`, `effective_domain`, `selected_specialization`, `reason`, `fallback_used`.

## Definitions

- **Fallback**: событие `specialization_fallback_used` или payload.fallback_used = true.
- **Weak execution lane**: высокая доля fallback по домену/шагу или по всем задачам в окне (например > 40% fallback или много general_*).
- **Hotspot**: domain+step или domain с числом fallback выше порога (например >= 2).

## Aggregation window

- Параметр `window_days` (по умолчанию 30). События с `created_at >= now - window_days`.

## Output shapes

### specialization_fallback_summary

- **purpose**: общая картина fallback за окно.
- **fields**: `total_fallback_events`, `total_selected_events`, `fallback_rate` (fallback / max(1, fallback+selected)), `unique_tasks_with_fallback`, `window_days`.
- **explainability**: числа из подсчёта событий по event_type.

### fallback_by_domain

- **purpose**: по каким доменам чаще fallback (payload.effective_domain).
- **fields**: list of `{ "domain_key", "fallback_count", "selected_count", "task_ids" }`.
- **explainability**: агрегация по payload.effective_domain.

### fallback_by_step

- **purpose**: по каким шагам чаще fallback (payload.workflow_step).
- **fields**: list of `{ "workflow_step", "fallback_count", "selected_count" }`.
- **explainability**: агрегация по payload.workflow_step.

### fallback_hotspots

- **purpose**: пары (domain, step) или домены с высокой концентрацией fallback.
- **fields**: list of `{ "domain_key", "workflow_step", "fallback_count", "reason_summary" }` или `{ "domain_key", "fallback_count" }`.
- **explainability**: порог (например >= 2) и явный reason_summary из типичного payload.reason.

### weak_execution_lane_summary

- **purpose**: сводка «слабых» execution lane (много general_* или fallback).
- **fields**: `general_dominant_count`, `fallback_dominant`, `recommendation_preview` (текстовая подсказка).
- **explainability**: на основе fallback_rate и доли general_* в selected_specialization.

### specialization_mismatch_summary

- **purpose**: задачи, где домен не general, но выбран general_* (из payload или из текущего suggest_specialization).
- **fields**: list of `{ "task_id", "effective_domain", "selected_specialization" }` или count по domain.
- **explainability**: определение mismatch из payload или из повторного вызова suggest для задач в окне (по необходимости ограничивать объём).
