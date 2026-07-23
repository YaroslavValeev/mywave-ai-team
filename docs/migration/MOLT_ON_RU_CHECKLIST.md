# Molt на RU — Owner GO

Статус: **GO live** (overlay + vendored service in Agents repo)  
Дата: 2026-07-24  
Файлы: `docker-compose.molt.yml`, `services/molt_http_service/`, `packages/shared-core/`

## Политика

- Порт **только** `127.0.0.1:8765` (не публиковать наружу).
- Governance `agm.mywavewake.ru` не зависит от Molt — rollback = `stop molt`.
- `MOLT_RUN_OWNER=1` в `.env` app — опциональный второй шаг (Agents→Molt writes).
- `docker-compose.molt.yml` монтирует общий volume `molt_data` в `/data` для **app** и **molt** (единый `canonical.db`).
- `Dockerfile` и overlay задают `PYTHONPATH=/app:/app/packages/shared-core` — иначе `shared_core` не импортируется в app-контейнере.

## Deploy (Owner GO)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
git pull origin main

# убедиться что в .env есть OWNER_API_KEY (уже есть)
# опционально для ready→Agents: AGENTS_CONTROL_ENABLED=1 (default в overlay)

docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml --profile molt up -d --build

# дождаться ready
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -sf http://127.0.0.1:8765/health && break
  sleep 2
done
curl -sS http://127.0.0.1:8765/health
curl -sS http://127.0.0.1:8765/ready
bash scripts/server_ops_check.sh
```

## Post-GO smoke (health + ready + POST /executions)

После `ready` ok — boundary smoke (ответ `accepted=false` для dummy task допустим):

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
export MOLT_HTTP_BASE_URL=http://127.0.0.1:8765
python3 scripts/molt/smoke_check_molt_http.py
```

Или одной строкой без скрипта:

```bash
curl -sS -X POST http://127.0.0.1:8765/executions \
  -H 'Content-Type: application/json' \
  -d '{"canonical_task_id":"smoke-check-dummy-task"}'
# ожидаем JSON с ключом "accepted" (true или false — оба ок для smoke)
```

## Включить запись Agents→Molt (шаг 2, после health/ready ok)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
grep -q '^MOLT_HTTP_BASE_URL=' .env || echo 'MOLT_HTTP_BASE_URL=http://molt:8765' >> .env
grep -q '^MOLT_TRANSPORT_MODE=' .env || echo 'MOLT_TRANSPORT_MODE=http' >> .env
grep -q '^MOLT_RUN_OWNER=' .env || echo 'MOLT_RUN_OWNER=1' >> .env
grep -q '^CANONICAL_PATH_ENABLED=' .env || echo 'CANONICAL_PATH_ENABLED=1' >> .env
# если ключи уже есть — поправьте значения вручную (nano .env)

docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml --profile molt up -d
bash scripts/server_ops_check.sh
python3 scripts/molt/smoke_check_molt_http.py
```

## Rollback

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml --profile molt stop molt
# опционально выключить writes:
# sed -i 's/^MOLT_RUN_OWNER=.*/MOLT_RUN_OWNER=0/' .env
# docker compose -f docker-compose.yml -f docker-compose.server-full.yml up -d
```
