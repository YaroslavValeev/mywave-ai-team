# MERGE PLAN

Статус: execution plan v1  
Дата: 2026-04-07

## 1) Цель доведения проекта до конца

Собрать единую систему из трёх слоёв с управляемой миграцией:

- Product Layer (`Personal_Helper`)
- Governance Layer (`Agents`)
- Runtime Layer (`Molt`)

При сохранении работоспособности текущего MVP и без массовой ломки кода.

## 2) Целевая структура (north star)

```text
project-os/
  apps/
    personal-helper/
  services/
    agents/
    molt/
  packages/
    shared-schema/
    shared-core/
    shared-policy/
    shared-auth/
    shared-logging/
    shared-integrations/
  docs/
    architecture/
    decisions/
    migration/
  infra/
  scripts/
```

Промежуточный шаг в текущем репо: `docs/*` + `packages/shared-*` как контрактная база.

## 3) Пошаговая последовательность

## Phase 0 — Baseline Lock

- Что делаем: freeze архитектурных решений и тестового baseline.
- Deliverables: `SYSTEM_CANON`, ADR-001..004.
- Зависимости: нет.
- Rollback point: возвращение к текущему working MVP (только docs changes).
- Совместимость: 100%.
- Автоматизируется Cursor Agents: да (документация/скелеты).
- Нужен ручной контроль Owner: подтверждение ADR.

## Phase 1 — Shared Contracts First

- Что делаем: фиксируем `shared-schema` и `shared-policy` контракты.
- Deliverables: schema/entity registry, policy/routing/approval contracts.
- Зависимости: Phase 0.
- Rollback point: отключение новых контрактов без удаления старых таблиц/API.
- Совместимость: через compatibility layer.
- Автоматизируется Cursor Agents: да (черновики контрактов, тестовые схемы).
- Ручной контроль Owner: validate критических policy правил.

## Phase 2 — Shared Store Evolution

- Что делаем: добавляем `Project`, `Run`, `Approval`, `MemoryEntry`, `ExecutionEvent`.
- Deliverables: миграции БД, repositories, API расширения.
- Зависимости: Phase 1.
- Rollback point: feature flag на новые сущности + dual-write off.
- Совместимость: старые endpoints продолжают работать.
- Автоматизируется Cursor Agents: частично (модели, репозитории, тесты).
- Ручной контроль Owner: approve миграций и data retention policy.

## Phase 3 — Adapter Layer

- Что делаем: адаптеры для текущих модулей на новые контракты.
- Deliverables: adapters для existing task lifecycle и event/audit bridge.
- Зависимости: Phase 2.
- Rollback point: возврат на legacy repositories.
- Совместимость: backward compatibility обязательна.
- Автоматизируется Cursor Agents: да.
- Ручной контроль Owner: smoke на прод-подобном стенде.

## Phase 4 — Governance Integration

- Что делаем: перенос governance contracts в выделенный слой (`Agents` semantics).
- Deliverables: стандартизованный decision/approval flow.
- Зависимости: Phase 3.
- Rollback point: feature flag governance-v2.
- Совместимость: legacy court/pipeline path доступен.
- Автоматизируется Cursor Agents: частично.
- Ручной контроль Owner: approve policy parity.

## Phase 5 — Runtime Integration

- Что делаем: закрепляем runtime owner (`Run` lifecycle, execution events, retries).
- Deliverables: persisted runs, orchestration traces, stop/resume semantics.
- Зависимости: Phase 4.
- Rollback point: fallback на deterministic runtime path.
- Совместимость: API contract не ломается.
- Автоматизируется Cursor Agents: частично.
- Ручной контроль Owner: проверка run controls.

## Phase 6 — Channel Unification

- Что делаем: Telegram + Cursor в едином lifecycle; dashboard parity на owner actions.
- Deliverables: channel parity matrix green.
- Зависимости: Phase 5.
- Rollback point: Telegram-only path.
- Совместимость: сохраняется.
- Автоматизируется Cursor Agents: да (API/UI wiring/tests).
- Ручной контроль Owner: сценарий approve/rework/clarify/merged вживую.

## Phase 7 — Cleanup & Deprecation

- Что делаем: deprecate legacy contracts, убрать дубли.
- Deliverables: удаление dead paths, migration notes, final runbooks.
- Зависимости: Phase 6 и стабилизация.
- Rollback point: tag/release перед cleanup.
- Совместимость: только после deprecation window.
- Автоматизируется Cursor Agents: частично.
- Ручной контроль Owner: финальное go/no-go.

**Статус (репозиторий MyWave_AI_TEAM_Presets, 2026-04-08):** Phase 7 — лёгкий проход (USAGE_AUDIT, MCP executor) **и** объединение синхронной оркестрации: `sync_run` + ADR-005. Deprecation legacy-схем и физическое слияние репозиториев Personal_Helper / Agents / Molt — отдельные этапы (см. раздел «не выполнено» ниже).

### Не выполнено в рамках текущего репо (north star)

| Пункт | Статус |
| --- | --- |
| Umbrella / monorepo `project-os` с `apps/personal-helper`, `services/agents`, `services/molt` | План и пакеты-черновики; перенос кода не начинался |
| Удаление legacy таблиц/полей | Только после окна deprecation + решение Owner |
| Полный smoke prod-like (живой Telegram + MCP) | Runbook оформлен (`docs/migration/FINAL_RUNBOOK.md`), автотесты API/паритета есть; живой Telegram/MCP smoke остаётся ручным |

## 4) Первые технические изменения (без массовой ломки)

1. Утвердить docs canon + ADR + migration.
2. Создать `packages/shared-schema` и `packages/shared-policy`.
3. Зафиксировать ID-policy (`task_id`, `run_id`) и approval contract.
4. Добавить тесты контрактов (schema/policy consistency).
5. Запустить Phase 2 миграции только после green tests и Owner sign-off.

## 5) KPI готовности по фазам

- Governance/Runtime boundary violations = 0.
- Дублирование task/run lifecycle engine = 0.
- Approval policy conflicts между каналами = 0.
- Contract tests pass = 100%.
- Full pytest remains green на каждом этапе.
