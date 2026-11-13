# COLLABORATION_EXECUTION_PLAYBOOK — Phase 11.4

## Suggestion → execution

- Вызвать `build_execution_from_suggestion` (API POST с телом suggestion) или создать из UI после просмотра suggestions.
- Если открытый execution с тем же fingerprint есть — возвращается существующий.

## Когда trigger

- Owner готов выполнить связанный safe step (например refresh decision queue, recheck Molt).
- Не вызывать массово без просмотра контекста.

## Закрытие

- После подтверждения что bottleneck снят: `close` с reason.
- Если safe action не помог — оставить `in_progress` или закрыть с reason «manual escalation».

## Проверка эффекта

- Система не утверждает автоматически снятие bottleneck; owner подтверждает closure.
