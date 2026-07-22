# SYSTEM CANON

Статус: draft v1  
Дата: 2026-04-07  
Назначение: каноническая модель единой системы из трёх слоёв.

> **Важно:** этот документ описывает **целевую (target) архитектуру** слияния Personal_Helper / Agents / Molt.  
> Текущий репозиторий `MyWave_AI_TEAM_Presets` реализует **Governance Layer (Agents)** и live control-plane на `agm.mywavewake.ru`.  
> Umbrella workspace Owner: `f:\Проекты MyWave\NEW2026\AI-Team` (`WORKSPACE_CANON.md`).  
> Карта слоёв: [docs/migration/LAYER_MAP.md](../migration/LAYER_MAP.md).  
> См. [PROJECT-STATUS.md](../PROJECT-STATUS.md) и [MERGE_PLAN.md](../migration/MERGE_PLAN.md).

## 1) Архитектурная формула (канон)

- `Personal_Helper` = Product Layer (внешний пользовательский слой, flagship).
- `Agents` = Governance Layer (control plane: routing, review, approval, audit).
- `Molt` = Runtime Layer (execution plane: orchestration runtime, tool execution, integrations runtime).

Это одна система из трёх слоёв, а не три конкурирующих продукта.

## 2) Layer Boundaries

- Product Layer отвечает за UX, пользовательские сценарии, presentation state, owner-facing surfaces.
- Governance Layer отвечает за policy-driven решения, маршрутизацию, суд/ревью, gating, traceability.
- Runtime Layer отвечает за выполнение шагов, планировщик выполнения, контроль фаз run, интеграции с внешними инструментами.

Запреты:
- Runtime Layer не становится пользовательским продуктом.
- Governance Layer не становится UI-продуктом.
- Product Layer не владеет policy и source of truth доменных сущностей.

## 3) Source of Truth

Единый владелец сущностей (единый store):

- `Project`
- `Task`
- `Run`
- `Decision`
- `Approval`
- `Artifact`
- `MemoryEntry`
- `ExecutionEvent`

`Agents` и `Molt` работают через единый контракт данных; запись в дублирующие локальные сторы не допускается.

## 4) Orchestrator Ownership

Канонический owner оркестрации: `Molt Runtime Layer`.

- `Molt` управляет жизненным циклом `Run`.
- `Agents` подключается как governance engine (triage, pipeline policy, roundtable, court, approval logic).
- `Personal_Helper` инициирует сценарий и отображает состояние.

## 5) Main Channels (MVP)

- Главный канал: `Telegram-first` (command + notify + approve).
- Исполнитель: `Cursor` (executor для code/content/docs/tasks).
- Web/Desktop интерфейсы: вторичные, с parity на основных owner actions.

## 6) Canonical Task Lifecycle

1. Owner command intake.
2. Task registration в SoT.
3. Governance routing (domain/task_type/criticality/plan_or_execute/execute_gate).
4. Runtime execution (pipeline steps + artifacts).
5. Governance review and court verdict.
6. Approval gate на критичных действиях.
7. Finalization, merge confirmation, completion.
8. Retention + audit preservation.

## 7) Anti-duplication Rules

- Один `task_id` на задачу, создаётся только в SoT.
- Один `run_id` на запуск, создаётся и ведётся только Runtime.
- Approval фиксируется в едином контракте (`Decision` + `Approval`), без параллельных статусов в каналах.
- Project memory хранится только в `shared-core`/SoT.
- Routing/policy хранятся только в shared policy package, не в prompt-only логике.

## 8) Migration Principles

- Без big-bang миграции, только фазовый переход.
- Сначала contracts/docs, потом schema/store, потом adapters/integration, затем cleanup.
- Backward compatibility обязательна до фазы deprecation.
- Каждый этап имеет rollback point.

## 9) Definition of Done для канона

Система считается канонически выровненной, когда:

- границы слоёв зафиксированы ADR и соблюдаются в коде;
- `Run`, `Approval`, `Project`, `MemoryEntry` формализованы и присутствуют в SoT;
- shared-schema и shared-policy вынесены в packages;
- один orchestration owner подтверждён (Runtime Layer);
- Telegram + Cursor интегрированы в единый lifecycle без дублирующих engine.
