# COLLABORATION_EXECUTION_LIFECYCLE — Phase 11.4

## Этапы

1. Suggestion существует (генерируется на лету).
2. **Execution candidate**: `build_execution_from_suggestion` создаёт или возвращает открытый execution с тем же fingerprint.
3. **Trigger**: owner явно вызывает trigger → при наличии safe action выполняется `execute_action`.
4. Статусы отражают прогресс; **task lifecycle не меняется**.

## Статусы

| Статус | Смысл |
|--------|--------|
| `available` | Создан, ждёт trigger |
| `triggered` | Trigger вызван |
| `in_progress` | Safe action не завершился успешно или ручной follow-up |
| `acknowledged` | Safe action успешно выполнен (или ручное подтверждение) |
| `closed` | Явно закрыт owner |
| `cancelled` | Отменён |

## Reopen

- Новый hotspot может породить новый execution с новым `execution_id` при том же fingerprint после закрытия предыдущего, либо отдельная запись — в baseline одна открытая запись на fingerprint.
