# ROLE_ACTION_ACCESS_MATRIX — Доступ к safe actions по ролям

Соответствует `allowed_roles` в action_center registry.

| Action | owner | operator | executor | reviewer |
|--------|-------|----------|----------|----------|
| refresh_status | ✓ | ✓ | ✓ | ✓ |
| refresh_project_view | ✓ | | ✓ | |
| send_summary_now | ✓ | | | |
| send_digest_now | ✓ | | | |
| recheck_molt_health | ✓ | ✓ | | |
| run_smoke_check | ✓ | ✓ | | |
| acknowledge_degraded | ✓ | ✓ | | |
| retry_runtime_check | ✓ | ✓ | | |
| rebuild_focus_list | ✓ | | | |
| notify_owner_now | ✓ | | | |
| open_decision_queue | ✓ | | | ✓ |
| trigger_project_summary | ✓ | | | |

## Проверка

- `can_execute_safe_action(role_key, action_name)` — делегирует в `action_center.can_execute_action(role, action_name)`.
- Перед выполнением: `role_access.can_execute_safe_action` + audit (`action_access_granted` / `action_access_denied`).
