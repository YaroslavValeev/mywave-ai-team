# Этап B — Шаг D: Molt HTTP (Runtime) локально

Статус: **closed** (Molt smoke + Agents→Molt E2E PASS + `agents_live` junction PASS)  
Дата: 2026-07-23 (post `f81bd26`)

## Роль

Molt = Runtime Layer. На RU AI-TEAM **не** деплоим Molt в этом шаге.  
Прод governance остаётся на `agm.mywavewake.ru`. Molt крутится на PC Owner.

## Критерии

- [x] Molt HTTP up (`:8765`) + `smoke_check_molt_http.py` OK (Owner PC)
- [x] Thin facade `app/canonical_bridge.py` на C:`main` (no-op без shared-core)
- [x] E2E script `scripts/integration/smoke_agents_molt_http_e2e.py` в umbrella
- [x] Повторный зелёный прогон E2E на локальном стеке (общий `canonical.db` + `/executions`) после recovery
- [x] Junction `services/agents_live` → C:`main` (`check_agents_pointer.ps1` PASS)

См. остаток: [POST_RECOVERY_REMAINING.md](POST_RECOVERY_REMAINING.md).

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
python scripts\integration\smoke_agents_molt_http_e2e.py
```

## Junction (Owner PC) — DONE

```powershell
cd "f:\Проекты MyWave\NEW2026\AI-Team"
powershell -ExecutionPolicy Bypass -File scripts\integration\check_agents_pointer.ps1
# RESULT: PASS — services\agents_live → C:\ProjectMyWave\MyWave_AI_TEAM_Presets_v1_1
# если FAIL (редко): New-Item Junction (Unicode-safe) через link_agents_pointer.ps1
```

## RU (только Control API)

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/system/health
# порт 8765 на RU не слушается — ожидаемо
```
