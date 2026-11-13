# PRODUCTION_READINESS_MODEL — Базис эксплуатационной готовности

## Критерии «готова к эксплуатации»

1. **Critical flows** — owner dashboard, API, Telegram, action center, collaboration execution, tuning/patch доступны и работают.
2. **Runtime entrypoints** — /health, /owner, /api/*, /actions отвечают; auth работает.
3. **Stores** — main DB (Postgres/SQLite) читаема/записываема; registry YAML читаемы.
4. **Backup readiness** — registry backup dir существует и записываем; postgres backup script присутствует (если Postgres).
5. **Patch/outcome paths** — registry_backups, apply/rollback работают; collaboration outcome persist.
6. **Key configs** — OWNER_API_KEY, TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID (или multi-role) настроены.

## Readiness levels

- **ready** — все обязательные checks passed.
- **degraded** — часть checks failed; система частично работоспособна; требуется внимание.
- **not_ready** — критичные checks failed; эксплуатация не рекомендуется.

## Readiness summary shape

- `ready: bool`
- `level: "ready" | "degraded" | "not_ready"`
- `failed_checks: list[{check_name, reason}]`
- `degraded_checks: list[{check_name, reason}]`
- `attention_items: list[str]` — 1–3 главных пункта для owner.
