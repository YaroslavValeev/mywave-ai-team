# ROLE_ACCESS_AUDIT_MODEL — Аудит доступа

## События (event_type)

| event_type | Когда | Payload (минимум) |
|------------|-------|-------------------|
| role_resolved | После resolve_actor_role | channel, actor_id?, role, fallback_used? |
| route_access_granted | Доступ к маршруту разрешён | route, role, actor |
| route_access_denied | Отказ в доступе к маршруту | route, role?, actor, reason |
| action_access_granted | Разрешено выполнение действия | action_name, role, actor |
| action_access_denied | Отказ в выполнении действия | action_name, role, actor, reason |
| unknown_role_fallback | Роль не определена, применён fallback | channel, actor_id?, fallback_role |

## Использование

- `log_role_access_event(repo, event_type, payload)` — через `log_audit(repo, event_type, task_id=None, payload=payload)`.
- Аудит не блокирует логику; пишет после факта (grant/deny).

## Корреляция

- `actor`: "web", "telegram:{chat_id}", "api" и т.д.
- При отказе — human-readable `reason` в payload для логов и ответов пользователю.
