# ADR-002: Source of Truth

- Статус: Accepted (draft baseline)
- Дата: 2026-04-07

## Контекст

Текущая система хранит ядро в `Task/Decision/Handoff/AuditEvent`, но целевой merge требует нормализованный единый SoT по всем слоям.

## Решение

Установить единый Source of Truth со следующими сущностями:

- `Project`
- `Task`
- `Run`
- `Decision`
- `Approval`
- `Artifact`
- `MemoryEntry`
- `ExecutionEvent`

Единый persistence owner: shared-core store.

## Правила

- `task_id` создаётся только SoT.
- `run_id` создаётся Runtime и персистится в SoT.
- Approval фиксируется в SoT-контракте, а не только как поле в канальных событиях.
- Память проекта хранится централизованно (`MemoryEntry`), не дублируется по слоям.

## Последствия

Плюсы:

- Один правдивый state для lifecycle и audit.
- Упрощение cross-layer интеграции.
- Контролируемая эволюция API.

Минусы:

- Нужны миграции БД и compatibility adapters.

## Переходный режим

До полной миграции допускается текущий набор таблиц, но все новые контракты проектируются с учётом финальной схемы SoT.
