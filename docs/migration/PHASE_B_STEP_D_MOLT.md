# Этап B — Шаг D: Molt HTTP (Runtime) локально

Статус: Molt local OK / Agents→Molt wiring in progress  
Дата: 2026-07-23

## Роль

Molt = Runtime Layer. На RU AI-TEAM **не** деплоим Molt в этом шаге.  
Прод governance остаётся на `agm.mywavewake.ru`. Molt крутится на PC Owner.

## Критерии

- [x] Molt HTTP up (`:8765`) + `smoke_check_molt_http.py` OK
- [x] Thin facade `app/canonical_bridge.py` на C:`main` (no-op без shared-core)
- [ ] Полный Agents→Molt HTTP E2E на локальном стеке (общий `canonical.db` + approve → `/executions`)
- [ ] Junction `services/agents_live` → C:`main` после проверки bridge call-sites

## Подготовка

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
powershell -ExecutionPolicy Bypass -File scripts\integration\ensure_molt_up.ps1
$env:MOLT_HTTP_BASE_URL="http://127.0.0.1:8765"
python scripts\molt\smoke_check_molt_http.py
```

## Agents HTTP mode

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
# .env.agents-http должен указывать на тот же CANONICAL_SQLITE_PATH, что и .env.molt
python scripts\runtime\start_agents_http_mode.py
python scripts\runtime\check_stack_status.py
```

## RU (только Control API)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/system/health
# порт 8765 на RU не слушается — ожидаемо
```
