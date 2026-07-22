# Integration: три слоя без big-bang monorepo

Статус: active  
Дата: 2026-07-22  
Связано: [LAYER_MAP.md](LAYER_MAP.md), umbrella `WORKSPACE_CANON.md`

## Цель этапа B

Связать Product / Governance / Runtime **по HTTP-контракту**, не сливая деревья в один git.

| Слой | Где код | Как стыкуется |
|------|---------|---------------|
| Personal_Helper | umbrella `AIProjectManager/` | → Agents Control API |
| Agents | `YaroslavValeev/mywave-ai-team` (prod clone / submodule) | SoT + Control API |
| Molt | umbrella `services/molt_http_service/` | execution; читает/синхронизирует статус через Control API при необходимости |

## Канон Control API

Base URL: `AGENTS_CONTROL_API_URL`  
Auth: `X-API-Key: $OWNER_API_KEY` (или `AGENTS_API_KEY`)

| Метод | Path | Кто вызывает |
|-------|------|--------------|
| GET | `/api/system/health` | PH, Molt, ops |
| POST | `/api/tasks` | PH (и Telegram уже внутри Agents) |
| GET | `/api/tasks`, `/api/tasks/{id}` | PH |
| POST | `/api/tasks/{id}/approve\|rework\|clarify` | PH (parity с Telegram) |
| POST | `/api/tasks/{id}/pipeline/run` | PH / automation |
| GET | `/api/tasks/{id}/runs`, `/execution-events` | Molt / PH status |
| GET | `/api/events` | PH timeline |

Клиент: `packages/agents-http-client/`.

## Направление вызовов (анти-дублирование)

```text
Owner (Telegram / PH UI)
        │
        ▼
   Agents Control API     ← единственный governance entry для create/approve
        │
        ├── SoT (Postgres / Agents store)
        └── MOLT_TRANSPORT_MODE=http → Molt :8765 /executions
                                              │
                                              └── optional: GET Agents /api/tasks/{id}
                                                  (status sync, не второй task engine)
```

**Запрещено:** создавать «второй» task lifecycle в Molt или PH SQLite как равноправный SoT.

## Umbrella: Agents pointer / sync

### Рекомендуемый режим (prod-dev)

Один канонический clone Agents на диске C: (уже в проде synced с `main`):

`C:\ProjectMyWave\MyWave_AI_TEAM_Presets_v1_1` @ `main`

Umbrella F: **не** править dirty копию `MyWave_AI_TEAM_Presets_v1_1` как SoT кода.  
Скрипт: `scripts/integration/link_agents_pointer.ps1` — junction `services/agents_live` → C: clone.

### Альтернатива: submodule

После очистки dirty tree в F-копии:

```powershell
# только когда F:\...\MyWave_AI_TEAM_Presets_v1_1 чистая или удалена
git submodule add https://github.com/YaroslavValeev/mywave-ai-team.git MyWave_AI_TEAM_Presets_v1_1
git submodule update --init --remote
```

Пока F-копия на чужой ветке с WIP — **не** делать submodule поверх.

### Sync команда (F-копия → main, осторожно)

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team\MyWave_AI_TEAM_Presets_v1_1"
git fetch origin
git stash push -u -m "pre-sync-agents"
git checkout main
git pull origin main
```

Rollback: `git checkout <old-branch>; git stash pop`

## Personal_Helper → Control API

Env:

```text
AGENTS_CONTROL_API_URL=https://agm.mywavewake.ru
# или локально http://127.0.0.1:8088
AGENTS_API_KEY=<OWNER_API_KEY>
AGENTS_CONTROL_ENABLED=1
```

Модуль: `AIProjectManager/agents_control_bridge.py`  
При `AGENTS_CONTROL_ENABLED=1` create/approve идут в Control API; legacy SQLite остаётся UX/cache.

## Molt → Control API

Env:

```text
AGENTS_CONTROL_API_URL=http://127.0.0.1:8088
AGENTS_API_KEY=<OWNER_API_KEY>
AGENTS_CONTROL_ENABLED=1
```

Модуль: `services/molt_http_service/agents_control.py`  
Использование: health probe в `/ready`, опционально `get_task` / `list_runs` по `canonical_task_id` ↔ Agents task id (crosswalk).

Agents → Molt по-прежнему: `MOLT_TRANSPORT_MODE=http`, `MOLT_HTTP_BASE_URL=http://127.0.0.1:8765`.

## Порядок внедрения

1. Зафиксировать Control API client в Agents repo (`packages/agents-http-client`) — **сделано**.
2. Umbrella: pointer/junction на C: `main` (не править отстающую F-копию).
3. PH bridge + env template.
4. Molt ready-check + optional get_task.
5. Smoke: PH create → Agents WAIT_OWNER → Telegram/Dashboard approve → Molt execution path.
6. Позже: submodule / физический layout `apps/` без смены контракта.

## Критерий готовности этапа B

- [x] Umbrella видит Agents `@ main` (junction `services/agents_live`)
- [x] `AgentsControlClient` + `scripts/smoke_agents_control.py` (+ `--full` / `--approve`)
- [x] PH: `agents_control_bridge` + crosswalk `agent_actions.agents_task_id` + hooks propose/apply
- [x] Molt `/ready` учитывает Agents health (если `AGENTS_CONTROL_ENABLED=1`)
- [x] Живой E2E Owner: create → WAIT_OWNER → approve → DONE (#4, #6, #7 auto_run на прод)
- [x] POST `/api/tasks` + `auto_run: true` (deployed)
- [ ] PH desktop live propose→approve against prod — см. [PHASE_B_STEP_C_PH.md](PHASE_B_STEP_C_PH.md)
- [ ] Agents→Molt HTTP execution on local stack (`MOLT_TRANSPORT_MODE=http`)

## Риски

| Риск | Митигация |
|------|-----------|
| Две копии Agents (C: vs F:) | Junction / только C: как code SoT |
| Рассинхрон task_id PH int vs Agents | crosswalk + хранить `agents_task_id` в PH |
| Approve policy в двух местах | только Agents Control API |
| Prod URL vs local | `AGENTS_CONTROL_API_URL` явно |
