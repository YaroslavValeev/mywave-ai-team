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
Пост-recovery: [POST_RECOVERY_REMAINING.md](POST_RECOVERY_REMAINING.md).

**Уже закрыто (Phase B):** junction `services/agents_live`, HTTP-клиент, PH Control bridge (headless/wiring/apply-path), Molt local E2E, живой prod approve (#11 DONE).

Остаток без big-bang:

1. Optional Owner PC: visual PH GUI one-click (`run_ph_with_control.ps1`).
2. Позже: git submodule / физический layout `apps/` без смены контракта.
3. Defer: Molt на RU, полный RU Dashboard RU-locale, CrewAI no-fallback guarantee.

Rollback: продолжать использовать только этот репозиторий как сейчас (MVP control-plane).
