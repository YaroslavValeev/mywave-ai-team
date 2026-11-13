# HANDOFF_EXECUTION_PLAYBOOK — Phase 11.4

## Handoff + execution

- Handoff signals остаются в collaboration_flows.
- Execution фиксирует **операционный ответ** (safe action или manual marker).

## Типичный поток

1. Виден handoff/hotspot → suggestion с `safe_action_available`.
2. Создать execution → trigger → при успехе acknowledged.
3. Закрыть execution когда handoff разрешён на уровне процесса (вне scope этого слоя — вручную).

## Без safe action

- `safe_action_key` null → только advisory; closure manual после работы вне системы.
