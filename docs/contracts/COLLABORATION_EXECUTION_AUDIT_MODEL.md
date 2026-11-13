# COLLABORATION_EXECUTION_AUDIT_MODEL — Phase 11.4

## События (event_type)

- `collaboration_execution_created`
- `collaboration_execution_triggered`
- `collaboration_execution_action_linked` — payload: execution_id, safe_action_key, action_id (из action_center)
- `collaboration_execution_closed`
- `collaboration_execution_acknowledged` — после успешного safe action
- `collaboration_execution_reopened` — при создании нового execution после закрытия (опционально)

## Payload (минимум)

`execution_id`, `suggestion_fingerprint`, `execution_status`, `safe_action_key`, `actor`.
