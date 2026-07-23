# Molt HTTP Service (Phase 8.1 / 8.2)

Минимальный HTTP API для Molt boundary. Реализует контракт из `shared_core.molt_transport`; runtime-логика живёт в shared-core, сервис — только транспортная оболочка. Phase 8.2: /ready, process entrypoint, observability.

## Endpoints

- `GET /health` → `{"status":"ok"}` — процесс поднят
- `GET /ready` → `{"status":"ready"}` или `{"status":"not_ready","reason":"..."}` — готов к приёму запросов (конфиг + runtime deps)
- `GET /metrics` → JSON операционной статистики (requests_total, requests_by_operation, accepted_total, deduplicated_total, avg_duration_ms и др.) — Phase 8.4
- `POST /executions` — CreateExecutionRequest → CreateExecutionResponse
- `POST /events` — EmitExecutionEventRequest → EmitExecutionEventResponse
- `POST /approvals/resolve-runtime` — ResolveApprovalRuntimeRequest → ResolveApprovalRuntimeResponse
- `POST /rework` — HandleReworkRequest → HandleReworkResponse

## Запуск (каноническая команда)

Из **корня репо** (PYTHONPATH выставляется скриптом):

```bash
python scripts/molt/start_molt_http.py
```

### Operational launch (Phase 8.5)

Для управляемого запуска с env-профилем и проверкой стека используйте wrapper и playbook:

- **Env:** скопируйте `infra/env/.env.molt.example` в `.env.molt` (в корне или в каталоге запуска), при необходимости отредактируйте.
- **Запуск Molt:** `python scripts/runtime/start_molt.py` — подгружает `.env.molt` и запускает `scripts/molt/start_molt_http.py`.
- **Проверка стека:** `python scripts/runtime/check_stack_status.py` — health, ready, metrics.
- **Полный сценарий:** см. [ROLLOUT_PLAYBOOK_HTTP_RUNTIME.md](../../docs/migration/ROLLOUT_PLAYBOOK_HTTP_RUNTIME.md) и [MOLT_RUNTIME_SUPERVISION.md](../../docs/migration/MOLT_RUNTIME_SUPERVISION.md).

Или вручную с entrypoint-модулем:

```bash
# Windows (PowerShell)
$env:PYTHONPATH = "packages\shared-core;services"
python -m uvicorn molt_http_service.app:app --host 0.0.0.0 --port 8765

# Linux/macOS
PYTHONPATH=packages/shared-core:services python -m uvicorn molt_http_service.app:app --host 0.0.0.0 --port 8765
```

Или через run.py (из корня, PYTHONPATH должен включать packages/shared-core и services):

```bash
PYTHONPATH=packages/shared-core:services python -m molt_http_service.run
```

## Smoke-check

После запуска сервиса:

```bash
python scripts/molt/smoke_check_molt_http.py
```

Или с явным URL: `MOLT_HTTP_BASE_URL=http://127.0.0.1:8765 python scripts/molt/smoke_check_molt_http.py`

## Конфиг (env)

- `MOLT_HTTP_HOST` — host (default 0.0.0.0)
- `MOLT_HTTP_PORT` — port (default 8765)
- Для canonical storage: `CANONICAL_PATH_ENABLED`, `CANONICAL_STORAGE`, `CANONICAL_SQLITE_PATH` и т.д. — см. docs/contracts/MOLT_RUNTIME_CONFIG.md

## Retry

Retry в HTTPMoltClient не реализован (см. ADR-017). Таймаут задаётся через `MOLT_HTTP_TIMEOUT_SEC`.
