# Domain override analytics model (Phase 10.5)

## Purpose

Агрегировать события domain override из audit и дать explainable сводки и hotspots для refinement.

## Source of truth

- **audit_events**: `event_type` in (`domain_override`, `domain_override_cleared`), `task_id`, `payload_json`, `created_at`.
- **tasks**: для task_id из событий — domain, task_type (для project_key proxy).

## Aggregation window

- Параметр `window_days` (по умолчанию 30). События учитываются с `created_at >= now - window_days`.

## Output shapes

### domain_override_summary

- **purpose**: общая картина override за окно.
- **fields**: `total_overrides`, `total_cleared`, `unique_tasks_with_override`, `window_days`, `override_rate` (optional: overrides / max(1, total_tasks_in_window)).
- **explainability**: все числа из подсчёта событий по типам.

### override_by_domain

- **purpose**: по какому домену чаще всего ставили override (payload.new_primary_domain).
- **fields**: list of `{ "domain_key", "count", "task_ids" }` sorted by count desc.
- **explainability**: каждая запись = события domain_override с данным new_primary_domain.

### override_by_project

- **purpose**: в каких «проектах» (project_key из task.domain/task_type) больше всего override.
- **fields**: list of `{ "project_key", "count", "task_ids" }`.
- **explainability**: project_key = _project_key(task); count = число событий override по задачам этого проекта.

### override_reason_patterns

- **purpose**: частые причины override (payload.reason или source).
- **fields**: list of `{ "reason_preview", "count" }` (reason обрезается до 50–80 символов).
- **explainability**: агрегация по payload.

### override_hotspots

- **purpose**: зоны, где override концентрирован — domain или project с count выше порога.
- **fields**: list of `{ "type": "domain"|"project", "key", "count", "reason_summary" }`.
- **explainability**: порог (например >= 2) и явное указание type и key.

## Severity / thresholds

- Override-heavy domain: count >= 2 за окно.
- Override-heavy project: count >= 2 за окно.
- Пороги задаются в heuristics; здесь только модель полей.
