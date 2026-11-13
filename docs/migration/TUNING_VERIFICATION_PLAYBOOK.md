# TUNING_VERIFICATION_PLAYBOOK — Phase 11.2

## Назначение

Playbook описывает verification tuning outcomes.

## Verification outcome

- **improved** — baseline signal снизился (fallback_count, override_count)
- **unchanged** — примерно то же
- **worse** — пост-apply хуже
- **insufficient_data** — мало данных за окно

## Как верифицировать

1. Применить patch (через refinement patch workflow)
2. Подождать verification_window_days (7–14)
3. Сравнить baseline vs post-apply по source_signals
4. POST /api/owner/tuning/{id}/verify с outcome
5. Telegram: /verify_tuning &lt;id&gt; improved|unchanged|worse

## Rule-based baseline

- Сравнение по тем же метрикам (fallback_count, override_count)
- Без магических scoring
- Owner принимает решение по наблюдаемым данным
