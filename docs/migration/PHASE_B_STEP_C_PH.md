# docs/migration/PHASE_B_STEP_C_PH.md — критерии Step C (обновлено 2026-07-23)
# Этап B — Шаг C: Personal_Helper → Control API

Статус: headless closed / GUI optional  
Дата: 2026-07-23

## Роль

Personal_Helper = product shell. Governance остаётся на `agm.mywavewake.ru`.  
Bridge: `AIProjectManager/agents_control_bridge.py` → `packages/agents-http-client`.

## Критерий шага C

- [x] Headless bridge smoke: propose→WAIT_OWNER→approve→DONE (**#8**, 2026-07-22)
- [x] Health: `enabled=True` + Control API `status=ok` (Owner PC / bridge)
- [ ] `run_ph_with_control.ps1` + GUI propose/apply (Owner, optional visual confirm)
- [ ] Apply → задача `DONE` через desktop UI

## Headless (без GUI) — основная проверка

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
powershell -ExecutionPolicy Bypass -File .\scripts\integration\run_ph_control_headless.ps1
# или:
python .\scripts\integration\smoke_ph_control_headless.py
```

## Desktop UX (опционально)

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
