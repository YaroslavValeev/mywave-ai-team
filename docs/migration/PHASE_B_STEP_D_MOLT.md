# Этап B — Шаг D: Molt HTTP (Runtime) локально

Статус: in progress  
Дата: 2026-07-22

## Роль

Molt = Runtime Layer. На RU AI-TEAM **не** деплоим Molt в этом шаге.  
Прод governance остаётся на `agm.mywavewake.ru`. Molt крутится на PC Owner.

## Подготовка (уже сделано агентами при возможности)

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
# .env.molt с CANONICAL_SQLITE_PATH=...\data\canonical.db
python scripts\runtime\start_molt.py
# отдельный терминал:
$env:MOLT_HTTP_BASE_URL="http://127.0.0.1:8765"
python scripts\molt\smoke_check_molt_http.py
```

Критерий: `smoke_check OK` + `/ready` → `ready`.

## Agents → Molt (локальный HTTP mode)

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
# Terminal A: Molt уже Up
# Terminal B:
copy infra\env\.env.agents-http.example MyWave_AI_TEAM_Presets_v1_1\.env.agents-http
# поправить CANONICAL_SQLITE_PATH на тот же data\canonical.db
# MOLT_HTTP_BASE_URL=http://127.0.0.1:8765
python scripts\runtime\start_agents_http_mode.py
python scripts\runtime\check_stack_status.py
```

## RU (только проверка Control API — Molt там нет)

```bash
cd /opt/mywave/ai-team
set -a; source .env; set +a
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/system/health
# Molt на 8765 с RU не слушается — это ожидаемо
```
