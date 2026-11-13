# Playbook: collaboration outcomes

## Как читать outcome
- **outcome_status** — что случилось с метрикой (improved / unchanged / worse / insufficient_data).
- **effectiveness_label** — человеко-удобная интерпретация (effective / partially_effective / ineffective / not_enough_signal).
- **outcome_reason** — краткое правило + числа «было → стало».
- **baseline_signal_state** / **post_execution_signal_state** — сырой explainable снимок.

## Когда execution считать effective
- После evaluate: `outcome_status=improved` и `effectiveness_label=effective`.
- Практически: целевая метрика для типа execution **снизилась** (см. `COLLABORATION_OUTCOME_HEURISTICS.md`).

## Когда нужен follow-up
- `followup_needed=true` или рекомендация `collaboration_execution_followup_signal`.
- Типично: сигнал не сдвинулся, данных мало, или ситуация ухудшилась.

## Если collaboration action не помог
- Открыть `/owner/collaboration/outcomes` — ineffective hotspots по типу и проекту.
- Пересмотреть **паттерн** (другой safe action, другой роль-фокус, уточнение постановки), а не только повторять тот же execution type.

## Owner / GM
- **Web:** `/owner/collaboration/outcomes`, блок на `/owner/collaboration`, карточка execution.
- **Telegram:** `/collaboration_outcomes`, `/collaboration_outcome <id> [evaluate]`, `/collaboration_followup`.
