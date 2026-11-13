# Tuning Verification Model (Phase 11.2)

## Поля

| Поле | Описание |
|------|----------|
| `verification_window_days` | Окно наблюдения post-apply (по умолчанию 7–14) |
| `baseline_signal_level` | Уровень сигнала до применения (fallback_count, override_count и т.п.) |
| `post_apply_signal_level` | Уровень после применения |
| `verification_outcome` | improved, unchanged, worse, insufficient_data |
| `verification_reason` | Краткое объяснение |
| `needs_followup` | bool — требуется ли ещё tuning |

## verification_outcome

- **improved** — baseline > post_apply (сигнал снизился)
- **unchanged** — примерно то же
- **worse** — пост-apply хуже
- **insufficient_data** — мало данных за окно

## Верификация

- Rule-based, explainable
- Сравнение baseline vs post_apply по тем же source_signals
- Owner вручную выставляет outcome при достаточном наблюдении
