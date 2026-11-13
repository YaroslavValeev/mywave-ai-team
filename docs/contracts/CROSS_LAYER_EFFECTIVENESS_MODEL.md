# Cross-layer effectiveness model (Phase 11.6)

## EffectivenessSlice (по слою)

| Поле | Описание |
|------|----------|
| `layer` | `tuning` \| `collaboration` |
| `window_days` | Окно агрегации |
| `effective_count` | Счётчик «улучшений» |
| `ineffective_count` | Счётчик «неэффективно» / worse |
| `followup_count` | Требуют follow-up |
| `total_in_window` | Всего outcomes в окне |
| `evidence_source` | Краткое описание источника (tuning_outcomes / collaboration_outcomes) |
| `evidence_refs` | Опционально: `[{id_type, id_value}]` для трассировки |

## CrossLayerEffectivenessSummary

| Поле | Описание |
|------|----------|
| `window_days` | Окно |
| `slices` | `[{ layer, effective_count, ineffective_count, ... }]` |
| `alignment_items` | `[{ headline, reason, evidence_refs, conflict_type }]` — рассогласования |
| `explainable` | `true` |
| `synthesized_at` | ISO timestamp (on-demand) |

## Конфликт (alignment_items)

| conflict_type | Условие |
|---------------|---------|
| `collaboration_improved_tuning_worse` | collaboration effective ≥1 и tuning worse ≥1 в окне |
| `both_need_followup` | followup по обоим слоям выше порога |

Evidence refs: `tuning_candidate_id`, `execution_id`, `outcome_id` — для трассировки.
