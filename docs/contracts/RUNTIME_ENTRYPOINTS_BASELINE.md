# RUNTIME_ENTRYPOINTS_BASELINE — Production-relevant entrypoints

## Entrypoints

| Route/Command | Auth | Critical |
|---------------|------|----------|
| /health | нет | да |
| /owner | require_owner_key | да |
| /owner/portfolio | require_owner_key | да |
| /owner/interventions | require_owner_key | да |
| /owner/decision-support | require_owner_key | да |
| /owner/readiness | require_owner_key | да (Phase 12.2) |
| /actions | require_owner_key | да |
| /actions/run | require_owner_key | да |
| /api/actions | require_owner_key | да |
| /api/owner/* | require_owner_key | да |
| /api/tasks/* | require_owner_key | да |
| Telegram /status, /actions, /do | is_owner | да |

## Route access audit

Для критичных entrypoints при `ROUTE_ACCESS_AUDIT_ENABLED=1` логируется `route_access_granted` (например для `/owner/readiness`). По умолчанию выключено, чтобы не спамить audit.
