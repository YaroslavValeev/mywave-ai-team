# Molt boundary observability model (Phase 8.4)

Минимальный operational layer для диагностики и сопровождения Molt HTTP boundary.

## Канонические лог-ключи

В логах сервиса и клиента используются единые ключи (JSON или key=value):

| Ключ | Описание |
|------|----------|
| `request_id` | Correlation key запроса |
| `trace_id` | Опциональный сквозной идентификатор трассировки |
| `operation` | Имя операции (executions, events, approvals_resolve_runtime, rework) |
| `endpoint` | HTTP path (/executions, /events, …) |
| `accepted` | Успех с точки зрения бизнес-логики |
| `deduplicated` | Ответ возвращён из idempotency receipt |
| `duration_ms` | Длительность обработки (мс) |
| `error_type` | transport_error \| business_rejection \| internal_error |
| `error_message` | Краткое описание ошибки (без чувствительных данных) |
| `transport_mode` | На клиенте: "http" |

## Request journal

Журнал boundary-запросов (audit trail). Поля записи:

- `request_id`, `trace_id`, `operation`, `endpoint`
- `accepted`, `deduplicated`
- `status`, `error_type`, `error_message`
- `created_at`, `duration_ms`

Хранилище: SQLite (MOLT_JOURNAL_SQLITE_PATH или CANONICAL_SQLITE_PATH). Ограничение размера: MOLT_JOURNAL_MAX_ENTRIES (по умолчанию 10000).

## Metrics (GET /metrics)

JSON с счётчиками:

- `requests_total` — всего boundary-запросов (POST)
- `requests_by_operation` — разбивка по операциям
- `accepted_total`, `rejected_total`
- `deduplicated_total`
- `transport_error_total`, `business_rejection_total` — на сервисе считаются по error_type при записи
- `health_checks_total`, `ready_checks_total`
- `avg_duration_ms` — средняя длительность (мс)
- `last_request_at` — время последнего boundary-запроса (ISO)

## Интерпретация accepted / rejected / deduplicated

- **accepted=true** — операция выполнена успешно с точки зрения runtime.
- **accepted=false** — бизнес-отклонение или внутренняя ошибка; в `error_message` причина.
- **deduplicated=true** — повторный запрос с тем же request_id; возвращён сохранённый результат, side effect не повторялся.

## /health, /ready, /metrics

- **GET /health** — процесс жив; быстрая проверка доступности.
- **GET /ready** — готовность к приёму runtime-операций (конфиг и deps инициализированы).
- **GET /metrics** — операционная статистика boundary; не подменяет health/ready.

## Ручная диагностика по request_id

1. Найти в логах сервиса строку с `request_id=<id>` (или в JSON-логе поиск по ключу).
2. Проверить journal: скрипт `scripts/molt/inspect_molt_runtime.py` может выводить последние записи из SQLite journal.
3. По request_id в journal видно: operation, endpoint, accepted, deduplicated, duration_ms, error_type, error_message, created_at.
4. На стороне клиента в логах искать тот же request_id для прослеживания полного пути запроса.
