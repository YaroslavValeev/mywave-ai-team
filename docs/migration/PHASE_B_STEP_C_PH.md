# Этап B — Шаг C: Personal_Helper → Control API

Статус: ready for Owner  
Дата: 2026-07-22

## Порядок

1. RU Control API жив (уже: `#7 DONE`, `auto_run` OK)
2. **Сейчас:** PH desktop → create/approve на `agm.mywavewake.ru`
3. Потом: локальный Molt HTTP (шаг D)

## PC — точные команды

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"

# один раз: создать env и вписать ключ
copy infra\env\.env.agents-control.example .env.agents-control
notepad .env.agents-control
# AGENTS_CONTROL_ENABLED=1
# AGENTS_CONTROL_API_URL=https://agm.mywavewake.ru
# AGENTS_API_KEY=<ваш OWNER_API_KEY>

# запуск PH с Control
powershell -ExecutionPolicy Bypass -File scripts\integration\run_ph_with_control.ps1
```

В UI:

1. Выбрать проект  
2. **AI: обновить план** → создаётся миссия на проде (ждите WAIT_OWNER / Telegram)  
3. **Применить предложения** → local apply + `approve` на Agents  

## RU — только проверка (параллельно)

```bash
ssh root@62.113.42.227
cd /opt/mywave/ai-team
set -a; source .env; set +a
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/system/health
# после propose из PH — список / последний id:
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/tasks \
  | python3 -c "import sys,json; t=json.load(sys.stdin); print([(x['id'],x['status']) for x in t[-5:]])"
```

## Критерий шага C

- [x] Headless bridge smoke: propose→WAIT_OWNER→approve→DONE (**#8**, 2026-07-22)
- [ ] `run_ph_with_control.ps1` + GUI propose/apply (Owner, optional visual confirm)
- [ ] Apply → задача `DONE` через desktop UI
