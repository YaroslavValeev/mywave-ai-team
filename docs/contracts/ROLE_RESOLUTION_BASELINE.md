# Role resolution baseline (Phase 9.7)

Как в baseline определяется роль и какие ограничения у подхода.

---

## Как сейчас определяется роль

- **Owner:** Уже задаётся конфигом (OWNER_CHAT_ID, owner_chat_id в Telegram; OWNER_API_KEY для dashboard). Доступ к owner-командам и dashboard только у этого идентификатора.
- **Operator / Executor / Reviewer:** В текущей реализации **не различаются по пользователю**. Role-scoped views доступны как **срезы контента**: один и тот же пользователь (owner) может открыть /views/operator или /view_operator и получить operator-срез. Роль задаётся **явным выбором view** (маршрут или команда), а не отдельным логином/ролью в системе.

## Возможные варианты baseline

1. **Query/command = role (текущий шаг):** Роль определяется тем, какой view запрошен (/views/operator → operator view). Кто может вызывать — по-прежнему только владелец dashboard (require_owner_key). Смысл: подготовить контент по ролям; раздача доступа по ролям — следующий этап.
2. **Config / allowlist:** В конфиге можно завести списки chat_id или user_id для ролей operator, executor, reviewer. При вызове /view_operator проверять, что chat_id в списке operator_allowlist (если задан), иначе отдавать только owner или отказ. В Phase 9.7 можно не реализовывать проверку, а только описать контракт.
3. **Simple mapping:** Один пользователь = одна роль из конфига (например TELEGRAM_OPERATOR_CHAT_ID). Тогда по chat_id определяется роль и показывается только её view. Тоже отложено на следующий этап.

## Ограничения baseline

- Нет полноценного RBAC: нет ролей в БД, нет permission matrix, нет «кто что может редактировать».
- Нет разной аутентификации по ролям: dashboard по-прежнему по OWNER_API_KEY; Telegram — по owner_chat_id для всех команд (если не введён отдельный allowlist).
- Role views — это в первую очередь **разные срезы одних и тех же данных** для разных ролей; enforcement «только operator видит operator view» можно добавить позже через config/allowlist.

## Почему это ещё не full RBAC

- Full RBAC подразумевает: сущности (users, roles), права (permissions), привязку user–role–permission, проверку при каждом действии. Сейчас есть только контент-срезы по ролям и один точка входа (owner). Роли задаются выбором view, а не учётной записью.

## Рекомендация для Phase 9.7

- Реализовать **role views и команды** (контент по ролям).
- **Не менять** текущую проверку доступа (owner only).
- В ROLE_RESOLUTION_BASELINE **зафиксировать**: роль = выбранный view (или в будущем — по config/allowlist по chat_id/user_id). Дальнейшее ужесточение — отдельный этап.
