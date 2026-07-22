# ADR-003: Orchestrator Ownership

- Статус: Accepted (draft baseline)
- Дата: 2026-04-07

## Контекст

В объединяемой системе критично исключить два равноправных orchestration engine.

## Решение

Orchestrator owner = `Molt` (Runtime Layer).

- Runtime управляет lifecycle `Run`.
- Governance (`Agents`) предоставляет policy decisions и review outcomes.
- Product (`Personal_Helper`) инициирует и отображает прогресс.

## Взаимодействие слоёв

1. Product отправляет команду на запуск задачи.
2. Runtime создаёт `Run` и управляет фазами выполнения.
3. Governance возвращает triage/pipeline/court решения.
4. Runtime сохраняет execution trace и artifacts.
5. Governance оформляет approval requirements.

## Почему так

- Разделяет execution и decision plane.
- Упрощает traceability и observability по `run_id`.
- Снижает риск конфликтующих state machines.

## Последствия

- Текущие runtime-состояния в памяти должны быть персистированы.
- Governance модули должны вызываться оркестратором, а не дублировать run lifecycle.
