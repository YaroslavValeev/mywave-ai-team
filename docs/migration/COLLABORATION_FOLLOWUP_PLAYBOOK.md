# Playbook: collaboration follow-up

## Цель
Связать **закрытый execution** с тем, остался ли bottleneck, без автономных повторных действий.

## Триггеры follow-up (системные)
- Outcome evaluate вернул `followup_needed=true`.
- Рекомендация `collaboration_execution_followup_signal` (≥2 таких outcomes в окне).
- Hotspot по проекту: `project_collaboration_needs_revisit`.

## Что делать owner
1. Проверить **почему** в outcome card (reason + baseline/post строки).
2. Если `insufficient_data` — дождаться большего окна или повторить evaluate с большим `window_days` (API).
3. Если `unchanged` / `worse` — эскалировать вручную (другой канал, уточнение задач, снятие блокеров).

## Явные non-actions
- Система **не** создаёт автоматически новый execution.
- Система **не** меняет approval/run pipeline.

## Метрики успеха follow-up
- Повторный evaluate после новых действий показывает `improved`.
- Hotspot исчезает из `get_collaboration_hotspots` (косвенно, через исходные сигналы).
