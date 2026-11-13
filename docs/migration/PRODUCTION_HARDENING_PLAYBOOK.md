# Production Hardening Playbook

## Цель

Довести систему до эксплуатационной зрелости: ключевые сценарии не хрупкие, ручная проверка воспроизводима, runbooks согласованы.

## Порядок проверки

1. **Readiness** — `/owner/readiness` или `/api/owner/readiness` или Telegram `/readiness`. Должно быть `ready` или `degraded` с понятными failed_checks.
2. **Critical flows** — owner dashboard, actions, collaboration, tuning работают.
3. **Store/backup** — DB доступна, registry YAML читаемы, backup dir writable.
4. **После изменений** — см. CRITICAL_FLOWS_SMOKE_CHECKLIST.

## Что проверять первым

1. `/health` — 200 OK.
2. `/owner/readiness` (с X-API-Key) — ready или список failed_checks.
3. `/owner` — dashboard загружается.
4. `/actions` — список действий.
5. Telegram `/status` — отвечает.

## Что проверять после patch/tuning/collaboration changes

1. `/owner/readiness` — нет новых failed checks.
2. Refinement proposals, tuning candidates — список загружается.
3. Collaboration executions — список загружается.
4. Apply patch — backup создаётся, apply успешен.

## Ссылки

- RUNBOOK.md — 502, SSL, .env, backup/restore.
- CRITICAL_FLOWS_SMOKE_CHECKLIST.md
- OWNER_DAILY_OPERATIONS_CHECKLIST.md
