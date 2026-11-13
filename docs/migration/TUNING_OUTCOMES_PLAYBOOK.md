# TUNING_OUTCOMES_PLAYBOOK — Phase 11.3

## Как читать outcome

- `baseline_signal_level` / `post_apply_signal_level` — текст + при наличии числа `fallback_count` по domain/step.
- `outcome_reason` — краткое rule-based объяснение сравнения.

## Когда tuning успешен

- `outcome_status: improved` и `improvement_detected: true`, либо ручной verify Phase 11.2 `improved` согласован с метриками.

## Если unchanged / worse

- Проверить профиль и домены задач; рассмотреть manual refinement; не запускать автоповтор apply.

## Если insufficient_data

- Увеличить `verification_window_days` или подождать накопления audit событий.

## Связь с Phase 11.2

- Ручной `/verify_tuning` остаётся; outcome layer дополняет автоматическим сравнением fallback metrics при наличии baseline после apply.
