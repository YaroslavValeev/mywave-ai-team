# ROLE_RESOLUTION_POLICY — Как определяется роль

## Текущая политика (Phase 12.1)

### Web

- Контекст: `api_key_valid=True` (после успешного `require_owner_key`).
- Результат: **owner** (web с валидным ключом = owner).

### Telegram

- Контекст: `chat_id`, `is_owner(chat_id)`.
- Если `is_owner(chat_id)` → **owner**.
- Иначе: в будущем — lookup по config (OPERATOR_CHAT_IDS, EXECUTOR_CHAT_IDS, REVIEWER_CHAT_IDS).
- Сейчас: **None** (deny).

### API

- Аналогично web: валидный API key → **owner**.

## Неопределённая роль

- `resolve_actor_role` возвращает `None` или пустую строку, если роль не определена.
- `deny_or_fallback_role(resolved)`:
  - если `resolved` в `KNOWN_ROLES` → вернуть как есть;
  - иначе → вернуть `None` (deny) или конфигурируемый fallback.

## Расширение (будущее)

- Env: `OPERATOR_CHAT_IDS`, `EXECUTOR_CHAT_IDS`, `REVIEWER_CHAT_IDS` — списки chat_id для ролей.
- Web: query param `?view=operator` при сохранении owner auth — для role-scoped views (не смена identity).
