# Cross-layer effectiveness synthesis rules

Все правила **детерминированы** в `app/services/cross_layer_effectiveness.py`.

## Входы (read-only)

- `get_tuning_outcome_summary(window_days)` → improved_count, worse_count, …
- `get_collaboration_effectiveness_summary(window_days)` → effective_executions_count, ineffective_executions_count, followup_needed_count, …

## Slice по слою

- **tuning:** `effective_count` = improved_count, `ineffective_count` = worse_count, followup из pending_measurement + unchanged + insufficient.
- **collaboration:** `effective_count` = effective_executions_count, `ineffective_count` = ineffective_executions_count, followup = followup_needed_count.

## Alignment (конфликты)

- **collaboration_improved_tuning_worse:** collaboration effective ≥1 **и** tuning worse ≥1.
- **both_need_followup:** followup по collaboration ≥2 **и** (pending + insufficient) по tuning ≥1.
- Порог для рекомендации в digest: **≥1** alignment item с conflict_type `collaboration_improved_tuning_worse` — строгий, чтобы не шуметь.

## Приоритет вывода

- Сначала показывать конфликты (alignment_items).
- Затем сводку по слоям (slices).
- Каждый alignment item содержит evidence_refs (id) для перехода в tuning/outcomes.
