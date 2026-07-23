# Molt на RU — чеклист (без live deploy)

Статус: **overlay ready / live = Owner GO**  
Дата: 2026-07-23  
Связано: [PHASE_B_STEP_D_MOLT.md](PHASE_B_STEP_D_MOLT.md), [POST_RECOVERY_REMAINING.md](POST_RECOVERY_REMAINING.md), `docker-compose.molt.yml`

## Политика

- Molt = Runtime Layer. На прод RU сейчас **только** governance (`agm.mywavewake.ru`).
- Overlay `docker-compose.molt.yml` с `profiles: [molt]` — **OFF by default** (без `--profile molt` не стартует).
- **Не** включать Molt на RU без явного GO владельца.
- **Не** публиковать `:8765` на `0.0.0.0` (в overlay только `127.0.0.1:8765`).
- Код сервиса — umbrella `services/molt_http_service`, **не** dirty F-копия Agents.

## Проверка «Molt выключен» (сейчас — норма)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
bash scripts/server_ops_check.sh
# секция «molt :8765» → OK: не слушает
ss -lntp | grep 8765 || echo "OK: порт 8765 не слушается"
```

## Будущий deploy (только после Owner GO)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a

# 1) путь к checkout molt_http_service на сервере (НЕ dirty F: Agents)
export MOLT_BUILD_CONTEXT=/opt/mywave/molt_http_service   # пример

# 2) env (в .env или export):
# AGENTS_CONTROL_API_URL=https://agm.mywavewake.ru
# AGENTS_API_KEY=$OWNER_API_KEY
# MOLT_RUN_OWNER=0   # включать 1 только когда готовы писать runs

# 3) start profile
docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml --profile molt up -d --build

# 4) smoke
curl -sS http://127.0.0.1:8765/health
curl -sS http://127.0.0.1:8765/ready

# 5) rollback
docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml --profile molt stop molt
```

## Rollback point

Governance AI-TEAM на nginx/8088 **не зависит** от Molt. Остановка Molt = safe.

## Что агенты не делают здесь

- Live `docker compose --profile molt up` на RU без Owner GO
- Big-bang monorepo / submodule поверх dirty F:
- Auto-merge в `main`
