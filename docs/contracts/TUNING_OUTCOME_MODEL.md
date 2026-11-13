# TUNING_OUTCOME_MODEL — Phase 11.3

Слой **verified outcomes** для tuning-изменений: что произошло с execution lane после patch (или почему оценка невозможна).

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `outcome_id` | str | `to_{tuning_candidate_id}` (один primary outcome на candidate в baseline) |
| `tuning_candidate_id` | str | |
| `proposal_id` | str \| null | |
| `patch_id` | str \| null | Последний известный patch_id |
| `verification_window_days` | int | Окно аналитики (default 14–30) |
| `baseline_signal_level` | str | Текстовое описание baseline (explainable) |
| `post_apply_signal_level` | str | Текущее состояние после apply |
| `baseline_fallback_count` | int \| null | Fallback events для пары domain/step (если известно) |
| `post_apply_fallback_count` | int \| null | То же на момент измерения |
| `outcome_status` | str | См. ниже |
| `outcome_reason` | str | Почему так решено |
| `improvement_detected` | bool | |
| `followup_needed` | bool | Нужен ли повторный review / manual |
| `measured_at` | str | ISO последней оценки |

## outcome_status

- `improved` — сигнал улучшился (напр. fallback_count снизился)
- `unchanged` — без существенного изменения
- `worse` — сигнал ухудшился
- `insufficient_data` — мало событий в окне
- `not_patch_applied` — proposal не в `applied` или patch не применялся
- `pending_measurement` — apply есть, baseline записан, post ещё не сравнивали

## Источники

- Audit: `specialization_fallback_used` по domain/step
- Proposal: `status`, `applied_at`, `source_tuning_candidate_id`
- Phase 11.2: ручной `verification_outcome` на candidate (дополняет, не заменяет explainable слой)
