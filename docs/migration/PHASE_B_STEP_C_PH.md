# docs/migration/PHASE_B_STEP_C_PH.md — критерии Step C (обновлено 2026-07-23)
# Этап B — Шаг C: Personal_Helper → Control API

Статус: **headless apply-path closed** / visual GUI = optional Owner  
Дата: 2026-07-23

## Роль

Personal_Helper = product shell. Governance остаётся на `agm.mywavewake.ru`.  
Bridge: `AIProjectManager/agents_control_bridge.py` → `packages/agents-http-client`.  
Crosswalk: `db.py` → `agent_actions.agents_task_id` (PySide **не** нужен для DB).

## Критерий шага C

- [x] Headless bridge smoke: propose→WAIT_OWNER→approve→DONE (**#8**, 2026-07-22)
- [x] Health: `enabled=True` + Control API `status=ok` (Owner PC / bridge)
- [x] GUI **wiring** verified (`smoke_ph_gui_wiring.py` — AST/hooks, без окна)
- [x] Headless **GUI apply-path** closed (`smoke_ph_gui_apply_headless.py`: bridge + SQLite crosswalk + approve→DONE) — без кликов; prod evidence **#14**, **#15** (2026-07-23)
- [ ] **Visual** GUI propose/apply one-click (`run_ph_with_control.ps1` + клик Owner) — **optional Owner PC**
- [ ] Visual Apply → задача `DONE` через desktop UI — **optional Owner PC**

См. остаток: [POST_RECOVERY_REMAINING.md](POST_RECOVERY_REMAINING.md).

## Headless (без GUI) — основная проверка

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
powershell -ExecutionPolicy Bypass -File .\scripts\integration\run_ph_control_headless.ps1
# или:
python .\scripts\integration\smoke_ph_control_headless.py
```

## Headless GUI apply-path (bridge + crosswalk, без кликов)

Тот же путь, что `projects_tab` propose→apply, без окна:

1. `create_task_via_agents` (mirror propose)
2. `save_agent_action` + `set_agent_action_agents_task_id` (crosswalk)
3. `mark_agent_action(applied)` + `approve_via_agents` через crosswalk (mirror apply)
4. печать `DONE status=...`

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
powershell -ExecutionPolicy Bypass -File .\scripts\integration\run_ph_gui_apply_headless.ps1
# или:
python .\scripts\integration\smoke_ph_gui_apply_headless.py
```

## Desktop UX (опционально — Owner)

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
powershell -ExecutionPolicy Bypass -File .\scripts\integration\run_ph_with_control.ps1
```

В UI: проект → **AI: обновить план** → **Применить предложения**.

## Проверка на RU (после propose)

```bash
ssh root@62.113.42.227
cd /opt/mywave/ai-team
set -a; source .env; set +a
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/system/health
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/tasks \
  | python3 -c "import sys,json; t=json.load(sys.stdin); print([(x['id'],x['status'],x.get('task_type')) for x in t[:5]])"
```
