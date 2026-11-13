# Molt runtime config (env)

Переменные окружения для Molt boundary и HTTP service. Phase 8.1/8.2.

## Transport mode (Agents / caller side)

| Переменная | Назначение | Default | Где используется | Влияние на режимы |
|------------|------------|---------|------------------|-------------------|
| `MOLT_TRANSPORT_MODE` | Режим: `local`, `stub`, `http` | `local` | shared_core.canonical_bridge._get_molt_client | local=in-process, stub=transport-shaped in-process, http=HTTPMoltClient |
| `MOLT_HTTP_BASE_URL` | Базовый URL Molt HTTP service (без trailing slash) | — | shared_core.feature_flags, HTTPMoltClient | Только при `http`: без URL fallback на local |
| `MOLT_HTTP_TIMEOUT_SEC` | Таймаут HTTP-запроса к Molt (сек) | `30` | shared_core.feature_flags, HTTPMoltClient | Только при `http` |
| `MOLT_HTTP_RETRIES` | Число повторов при transport failure (Phase 8.3) | `0` | shared_core.feature_flags, HTTPMoltClient | Только при `http`; retry только при transport_error |

## Molt HTTP service (server side)

| Переменная | Назначение | Default | Где используется | Влияние |
|------------|------------|---------|------------------|---------|
| `MOLT_HTTP_HOST` | Host для bind | `0.0.0.0` | molt_http_service.config | Сервис |
| `MOLT_HTTP_PORT` | Порт | `8765` | molt_http_service.config | Сервис |
| `MOLT_IDEMPOTENCY_SQLITE_PATH` | Путь к SQLite для idempotency receipts (Phase 8.3) | как CANONICAL_SQLITE_PATH | molt_http_service.idempotency | Если не задан — используется in-memory store |

## Canonical path (общие для storage; нужны сервису при CANONICAL_PATH_ENABLED)

| Переменная | Назначение | Default | Влияние |
|------------|------------|---------|---------|
| `CANONICAL_PATH_ENABLED` | Включить запись в shared-core | — | Без 1/true — storage не инициализируется, readiness может быть not_ready |
| `CANONICAL_STORAGE` | Бэкенд: `memory`, `sqlite` | `memory` | Сервис и shared-core |
| `CANONICAL_SQLITE_PATH` | Путь к SQLite (при sqlite) | — | Обязателен при CANONICAL_STORAGE=sqlite |
| `CROSSWALK_BACKEND` | `memory` / `sqlite` | см. shared-core | Сервис и shared-core |
| `CROSSWALK_SQLITE_PATH` | Путь (опционально) | как CANONICAL_SQLITE_PATH | shared-core |

## Run ownership (Agents side)

| Переменная | Назначение | Default | Влияние |
|------------|------------|---------|---------|
| `MOLT_RUN_OWNER` | Molt владеет Run; Agents запрашивает execution у Molt | — | При 1/true — request_execution_from_molt и т.д. |

Логика выбора клиента: при `MOLT_TRANSPORT_MODE=http` и заданном `MOLT_HTTP_BASE_URL` используется HTTPMoltClient; иначе при `http` — fallback на local с предупреждением в лог.
