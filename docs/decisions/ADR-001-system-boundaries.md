# ADR-001: System Boundaries

- Статус: Accepted (draft baseline)
- Дата: 2026-04-07

## Контекст

Система объединяет три существующих проекта: `Personal_Helper`, `Agents`, `Molt`.  
Нужно устранить role mixing и закрепить границы ответственности.

## Решение

Принять канонические границы:

- `Personal_Helper` = Product Layer (user-facing).
- `Agents` = Governance Layer (routing/review/approval/audit).
- `Molt` = Runtime Layer (execution/orchestration/integrations runtime).

## Последствия

Плюсы:

- Прозрачная ответственность по слоям.
- Снижение дублирования логики и конфликтов policy.
- Управляемая миграция без big-bang.

Ограничения:

- Требуется адаптерный период для существующих модулей.
- Любая новая функциональность должна проверяться на соответствие layer boundary.

## Scope изменений

- Документация архитектуры и миграции.
- Контракты shared-schema и shared-policy.
- Постепенная декомпозиция текущих модулей по слоям.
