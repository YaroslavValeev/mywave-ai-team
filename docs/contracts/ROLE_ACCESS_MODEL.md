# ROLE_ACCESS_MODEL — Модель ролей и доступа

## Роли

| Роль | Описание | Scope |
|------|----------|-------|
| **owner** | Владелец системы; полный доступ к portfolio, interventions, approvals, actions, config. | Все маршруты, все safe actions. |
| **operator** | Оператор: статус, recovery actions (recheck, smoke, acknowledge_degraded), views. | Ограниченный набор маршрутов и действий. |
| **executor** | Исполнитель: project/task views, refresh_project_view, refresh_status. | Ещё более ограниченный. |
| **reviewer** | Ревьюер: decision queue, approvals, open_decision_queue. | Фокус на review/approval. |

## Каналы (channel)

- **web** — Dashboard / API; auth через X-API-Key / OWNER_API_KEY.
- **telegram** — Telegram bot; auth через chat_id (OWNER_CHAT_ID, в будущем — mapping по ролям).
- **api** — прямой API (тот же, что web, но может отличаться в будущем).

## Resolution

Роль определяется через `resolve_actor_role(channel, context)`:

- `channel`: "web" | "telegram" | "api"
- `context`: `{api_key_valid?, chat_id?, is_owner?}` и т.д.

См. ROLE_RESOLUTION_POLICY.

## Fallback при неопределённой роли

- `deny_or_fallback_role(resolved)` — если роль не распознана или `None`, возвращается safe fallback:
  - по умолчанию: `None` (deny) — доступ не предоставляется;
  - при необходимости: конфигурируемый fallback (например "viewer" для read-only).

## Границы

- Роль — логическая группа, а не отдельная учётная запись.
- Один ключ / один chat_id может соответствовать одной роли.
- Multi-role (один субъект — несколько ролей) — на будущее.
