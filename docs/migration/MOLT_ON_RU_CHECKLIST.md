# Molt на RU — чеклист (без live deploy)

Статус: **draft / Owner GO required**  
Дата: 2026-07-23  
Связано: [PHASE_B_STEP_D_MOLT.md](PHASE_B_STEP_D_MOLT.md), [POST_RECOVERY_REMAINING.md](POST_RECOVERY_REMAINING.md)

## Политика

- Molt = Runtime Layer. На прод RU сейчас **только** governance (`agm.mywavewake.ru`).
- Локальный Molt на Owner PC уже закрыт (Phase B Step D).
- **Не** включать Molt на RU без явного GO владельца.
- **Не** публиковать `:8765` наружу без auth.
- Код сервиса — umbrella `services/molt_http_service`, **не** dirty F-копия Agents.

## Проверка «Molt выключен» (сейчас — норма)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/system/health
ss -lntp | grep 8765 || echo "OK: порт 8765 не слушается"
```

## Будущий deploy (только после Owner GO)

1. Доставить `molt_http_service` + `shared-core` на сервер (отдельный каталог, не смешивать с dirty F:).
2. `.env.molt`: общий `CANONICAL_SQLITE_PATH` / Postgres path; `AGENTS_CONTROL_API_URL=https://agm.mywavewake.ru`; `AGENTS_API_KEY=$OWNER_API_KEY`.
3. Compose profile `molt` (когда появится overlay в репо) — `up -d` **без** публикации 8765 на 0.0.0.0.
4. Smoke: `curl http://127.0.0.1:8765/health` и `/ready`.
5. Rollback: `docker compose … stop molt`; Agents продолжает работать без `MOLT_RUN_OWNER`.

## Rollback point

Governance AI-TEAM на nginx/8088 **не зависит** от Molt. Остановка Molt = safe.

## Что агенты не делают здесь

- Live `docker compose up` Molt на RU
- Big-bang monorepo / submodule поверх dirty F:
- Auto-merge в `main`
