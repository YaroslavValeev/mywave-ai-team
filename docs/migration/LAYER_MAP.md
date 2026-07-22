# Layer map — этот репозиторий в Project OS

Статус: active  
Дата: 2026-07-22

## Роль этого репо

`mywave-ai-team` / `MyWave_AI_TEAM_Presets_v1_1` = **Governance Layer (Agents)**.

| Слой | Код | Где живёт |
|------|-----|-----------|
| Product (Personal_Helper) | `AIProjectManager` | Umbrella: `…/NEW2026/AI-Team/AIProjectManager` + pointer `apps/personal-helper/` |
| Governance (Agents) | **этот репозиторий** | GitHub `YaroslavValeev/mywave-ai-team` + umbrella `services/agents/` |
| Runtime (Molt) | `molt_http_service` | Umbrella: `…/NEW2026/AI-Team/services/molt_http_service` |

Канонический umbrella workspace (локально Owner):  
`f:\Проекты MyWave\NEW2026\AI-Team` — см. `WORKSPACE_CANON.md` там.

## Что уже сделано в Agents-репо

- SoT: Task / Run / Approval / MemoryEntry / ExecutionEvent (миграции 003–007)
- Shared contracts: `packages/shared-schema/`, `packages/shared-policy/`
- Единый sync orchestration: `app/orchestrator/sync_run.py`
- Control API разбит: `app/dashboard/api/*`
- Production: Telegram + nginx `agm.mywavewake.ru`

## Следующие шаги слияния (без big-bang)

1. Umbrella `services/agents` → git submodule / path pointer на этот remote.
2. Molt HTTP service вызывает Agents Control API (`/api/tasks/...`) как единственный governance entry.
3. Personal_Helper UI ходит в тот же API (parity с Telegram/Dashboard).
4. `packages/shared-core` в umbrella — единственный SoT client; Agents остаётся owner store.

Rollback: продолжать использовать только этот репозиторий как сейчас (MVP control-plane).
