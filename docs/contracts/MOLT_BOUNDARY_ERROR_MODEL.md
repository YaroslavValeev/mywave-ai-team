# Molt boundary error model (Phase 8.3)

Единообразное представление ошибок на HTTP boundary между клиентом и сервисом.

## Типы ошибок

| Тип | Описание | Где возникает | Поведение клиента |
|-----|----------|---------------|-------------------|
| **transport_error** | Сеть, таймаут, connection refused, 5xx без тела | HTTPMoltClient при URLError/TimeoutError/HTTPError | Retry по политике (если request_id и idempotent); логируем endpoint, request_id, attempt |
| **service_not_ready** | Сервис не готов (readiness failed) | Не в рамках одного POST; отдельно GET /ready | Клиент не повторяет POST из-за not_ready; вызывающая сторона может повторить вызов позже |
| **business_rejection** | Сервис ответил 200, accepted=false | Любой POST, когда runtime отклонил операцию | Не retry; логируем business_rejection, reason; возвращаем response как есть |
| **malformed_response** | Тело ответа не JSON или нет ожидаемых полей | HTTPMoltClient при разборе ответа | Считать transport_error или отдельный тип; не retry по умолчанию |
| **idempotency_conflict** | Не используется в текущей реализации | — | При повторном request_id сервис возвращает deduplicated=true, не конфликт |
| **internal_error** | Исключение в handler до/после runtime | Сервис возвращает 500 или accepted=false, error_message | Клиент видит как HTTP 500 (transport_error) или 200+accepted=false (business_rejection) |

## Требования

- **В логах** клиента и сервиса явно различать: transport_error, business_rejection.
- **В response** при accepted=false всегда есть error_message (и при необходимости request_id).
- **Клиент** не маскирует ошибки: при transport_error после retries возвращает последний error_message; при business_rejection возвращает ответ без retry.
- **Сервис** при исключении в handler возвращает JSON с accepted=false, error_message, request_id.

## Retry policy

- Retry только при **transport_error**.
- Retry только если запрос идёт с **request_id** (idempotent contract).
- Число попыток: MOLT_HTTP_RETRIES; между попытками — backoff.
- При получении любого корректного ответа (в т.ч. deduplicated) retry не выполняется.
