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

Подробный контракт: [INTEGRATION_THREE_LAYERS.md](INTEGRATION_THREE_LAYERS.md).

1. Umbrella: Agents pointer/junction на prod clone `@ main` (`scripts/integration/link_agents_pointer.ps1`).
2. HTTP-клиент: `packages/agents-http-client` → PH и Molt.
3. Personal_Helper → Control API (`AGENTS_CONTROL_ENABLED=1`).
4. Molt → Control API health/status (не второй task engine); Agents→Molt через `MOLT_HTTP_*`.
5. Smoke: PH create → WAIT_OWNER → approve → execution.
6. Позже: git submodule / физический layout `apps/` без смены контракта.

Rollback: продолжать использовать только этот репозиторий как сейчас (MVP control-plane).
