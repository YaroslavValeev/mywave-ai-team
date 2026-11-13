# Collaboration outcome audit model

Используется тот же паттерн, что и для collaboration execution: `log_audit` с `task_id=None`.

## События
| event_type | Когда | Payload (минимум) |
|------------|-------|-------------------|
| `collaboration_outcome_evaluated` | После evaluate | `execution_id`, `outcome_id`, `outcome_status`, `effectiveness_label` |
| `collaboration_outcome_followup_needed` | Нужен follow-up | `execution_id`, `outcome_id`, `reason` / `outcome_status` |
| `collaboration_execution_effective` | Улучшение сигнала | `execution_id`, `outcome_id`, `primary_metric` |
| `collaboration_execution_ineffective` | Ухудшение / явная неэффективность | `execution_id`, `outcome_id`, `outcome_status` |

## Принципы
- Не логировать полные bundle в audit (только краткие поля); детали в JSON store.
- Не дублировать task lifecycle события.
