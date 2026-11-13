# ADR-050: Cross-layer effectiveness synthesis

## Статус
Accepted (Phase 11.6)

## Контекст
После Phase 11.3 (tuning outcomes) и Phase 11.5 (collaboration outcomes) owner/GM видят эффективность **по отдельным слоям**, но не согласованную картину: что улучшилось в целом, где слои расходятся (collaboration improved, tuning worse), и куда смотреть для принятия решения.

## Решение
Вводится **read-only synthesis layer** (без переноса SoT):
- `synthesize_cross_layer_summary(window_days)` — объединяет tuning + collaboration summaries;
- `get_layer_alignment_signals()` — выявляет конфликты (collaboration effective + tuning worse и т.п.);
- одна страница `/owner/effectiveness`, API, Telegram;
- одна рекомендация в digest при сильном рассогласовании (строгий порог).

## Границы
- **Источники истины по слоям:** tuning_outcomes, collaboration_outcomes (существующие stores).
- **Не делаем:** opaque scoring, авто-действия, изменение Run/Task/Approval lifecycle, LLM как источник метрик.
- **Только чтение** — synthesis не пишет в task/run/approval.

## Non-goals
- Полноценная performance analytics platform.
- Автоматическая корректировка ролей/паттернов.
- Merge tuning и collaboration stores в один.
