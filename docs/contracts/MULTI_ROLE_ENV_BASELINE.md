# MULTI_ROLE_ENV_BASELINE — Env-конфигурация для multi-role (Telegram)

## Текущие env (обязательные)

- `OWNER_API_KEY` — ключ для web/API.
- `TELEGRAM_BOT_TOKEN` — бот.
- `OWNER_CHAT_ID` — chat_id владельца (один).

## Multi-role env (Phase 12.2 baseline)

| Env | Описание | Формат |
|-----|----------|--------|
| `OPERATOR_CHAT_IDS` | Список chat_id с ролью operator | CSV: `123,456,789` |
| `EXECUTOR_CHAT_IDS` | Список chat_id с ролью executor | CSV |
| `REVIEWER_CHAT_IDS` | Список chat_id с ролью reviewer | CSV |

## Resolution order

1. Если chat_id == OWNER_CHAT_ID → owner.
2. Иначе, если chat_id в OPERATOR_CHAT_IDS → operator.
3. Иначе, если chat_id в EXECUTOR_CHAT_IDS → executor.
4. Иначе, если chat_id в REVIEWER_CHAT_IDS → reviewer.
5. Иначе → deny.

## Проверка baseline

- Наличие и парсинг OPERATOR_CHAT_IDS, EXECUTOR_CHAT_IDS, REVIEWER_CHAT_IDS (если заданы).
- resolve_actor_role("telegram", {chat_id, ...}) возвращает соответствующую роль.
