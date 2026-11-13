# Intervention Acceptance Loop Model (Phase 12.3)

## Response types

| response | Описание |
|----------|----------|
| deferred | Owner отложил — не показывать в do_now N часов |
| accepted | Owner принял (выполнил вручную или /do) — опционально |

## Хранение

- **audit_events**: `event_type=intervention_owner_response`
- **payload**: `{intervention_id, scope_type, scope_key, response, actor, defer_hours?, created_at?}`

## Deferral policy

- По умолчанию `defer_hours=24`.
- При построении do_now: исключить interventions с `intervention_id` в `get_recently_deferred_ids(hours=24)`.

## Entrypoints

- Telegram: `/defer_intervention <intervention_id>`
- Web: POST `/api/owner/intervention/defer` body `{intervention_id}`
- Dashboard: кнопка «Отложить» на intervention card.
