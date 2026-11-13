# Refinement backlog model (Phase 10.5)

Список actionable предложений по улучшению domain/specialization layer. Только рекомендации; выполнение вручную или отдельным workflow.

## Item shape

- **refinement_item_key**: уникальный идентификатор (например `override_heavy:legal`, `fallback:programming_engineer:pipeline`).
- **item_type**: `"override_heavy_domain"` | `"override_heavy_project"` | `"fallback_hotspot"` | `"mismatch_concentration"` | `"weak_lane"`.
- **domain_key**: если применимо.
- **workflow_step**: если применимо (pipeline, roundtable, court).
- **project_key**: если применимо.
- **severity**: `"low"` | `"medium"`.
- **reason**: краткое объяснение (1–2 предложения).
- **recommended_change**: что сделать:
  - add/expand specialization profile
  - improve routing keywords
  - review alias map
  - tighten fallback behavior
  - inspect override reasons manually
- **evidence_summary**: числа и scope (counts, window).
- **window_days**: за какой период посчитано.

## Backlog list

- Список items, отсортированный по severity (medium first), затем по count/relevance.
- Лимит (например 20) для отображения.
- **explainable**: каждый item выводится из refinement signals и analytics; без opaque priority score.

## Non-goals

- Не хранить backlog в БД как отдельную сущность (генерируется на лету из analytics).
- Не автоматически применять recommended_change (только подсказка owner/GM).
