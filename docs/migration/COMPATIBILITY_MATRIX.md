# COMPATIBILITY MATRIX

Статус: draft v1 (updated 2026-07-23)  
Дата: 2026-04-07 / refresh 2026-07-23

## 1) Источники и целевые роли

| Source | Берём как есть | Рефакторим | Откладываем |
|---|---|---|---|
| Personal_Helper | UX shell, user interaction model, project/task UX идеи | routing/policy из prompt в shared-policy, нормализация Task/Run/Decision/Approval | desktop-first assumptions |
| Agents | pipeline/roundtable/court, approve gates, audit trail | ввод Project/Run/Approval контрактов, вынос shared contracts | глубокая автономизация до стабилизации SoT |
| Molt | runtime orchestration подход, integration mindset | storage owner formalization, execution contracts через SoT | превращение в user-facing продукт |

## 2) Контракты и совместимость

| Область | Текущее | Целевое | Совместимость |
|---|---|---|---|
| Task ID | DB-generated task_id | same | backward compatible |
| Run ID | in-memory runtime id | persisted Run entity | compatibility adapter required |
| Approval | часть Decision/статусов | явный Approval contract | staged migration |
| Artifacts | handoff/report/verdict files + metadata in handoffs | Artifact entity + indexed metadata | dual mode until migration complete |
| Memory | фрагментирована | MemoryEntry in shared-core | adapter + backfill |
| Policy | YAML + часть логики в коде | shared-policy contracts | refactor-in-place with parity tests |

## 3) Каналы и действия owner

| Канал | Intake | Approve/Rework/Clarify | Merge confirm | Статус |
|---|---|---|---|---|
| Telegram | yes | yes | yes | main MVP channel |
| Dashboard/API | yes | partial/depends on endpoint surface | yes | parity in progress |
| MCP/Cursor | yes | через API tools/flow | yes | parity in progress |
| Desktop (PH GUI) | yes (via Control API) | yes (bridge) | via API | optional Owner PC (Phase B headless closed) |

## 4) Что ломается при переходе (и как закрыть)

1. `Run` из runtime memory в DB:
   - риск: потеря совместимости UI/runtime snapshot;
   - mitigation: adapter, который публикует старый snapshot contract.

2. Approval normalization:
   - риск: рассинхрон owner actions между Telegram/API;
   - mitigation: единый approval service + contract tests.

3. Policy centralization:
   - риск: расхождение YAML и кодовой логики;
   - mitigation: policy parity tests для critical actions.

## 5) Критерий совместимости

- Текущие API сценарии (`create -> pipeline -> approve -> merged`) остаются рабочими.
- Telegram owner flow не деградирует.
- MCP flow не теряет control operations.
- Все новые сущности вводятся через additive migrations.
