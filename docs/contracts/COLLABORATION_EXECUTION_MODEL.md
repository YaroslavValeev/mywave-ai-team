# COLLABORATION_EXECUTION_MODEL — Phase 11.4

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `execution_id` | str | `ce_{uuid}` |
| `suggestion_id` | str \| null | Краткий id из suggestion snapshot (если был) |
| `suggestion_fingerprint` | str | Стабильный ключ `sf_{sha256...}` |
| `suggestion_snapshot` | object | Копия suggestion на момент создания |
| `execution_type` | str | См. примеры ниже |
| `subject_type` | str | task, project, portfolio, collaboration_hotspot, role |
| `subject_key` | str | id проекта, task id, portfolio, и т.д. |
| `source_role` | str | Кто инициирует контекст |
| `target_role` | str | Кому адресовано действие |
| `execution_status` | str | lifecycle |
| `execution_reason` | str | Зачем создан execution |
| `safe_action_key` | str \| null | Ключ из action center или null |
| `last_action_result` | str \| null | Краткий результат последнего safe action |
| `created_at` | str | ISO |
| `updated_at` | str | ISO |
| `closed_at` | str \| null | ISO |
| `closure_reason` | str \| null | |
| `actor` | str \| null | Кто trigger/close |

## execution_type (примеры)

- `request_review` / `request_decision_resolution`
- `request_owner_attention`
- `request_operator_check`
- `escalate_runtime_issue`
- `mark_handoff_followup`
- `acknowledge_collaboration_gap`

## Связи

- suggestion (ephemeral) → fingerprint → execution (persistent)
- execution → optional `safe_action_key` → `action_center.execute_action`
