# Следующая волна — что можно / нельзя

Дата: 2026-07-24  
Контекст: RU/Molt/ops scope **закрыт**. Ниже — бывший «остаток».

## Матрица решений

| Пункт | Решение | Почему |
|-------|---------|--------|
| Visual PH GUI one-click | **done** (Owner PC, 2026-07-24) | #19 DONE; «Применено. Создано задач: 8» |
| `CURSOR_API_KEY` | **done** (Owner PC, 2026-07-24) | `setx` + live `Agent.prompt` smoke → `SDK_SMOKE_OK` |
| CrewAI без fallback | **Опционально на RU** (флаг) | При падении LLM миссии падают hard; не default |
| Полный TG-stream каждой реплики | **Не сейчас** | Шум/лимиты TG/стоимость; уже есть stage-notify |
| Auto-merge в `main` | **Запрещено** | Runner policy + git safety: merge только Owner |
| Big-bang monorepo | **Запрещено взрывом** | Только по MERGE_PLAN инкрементально (уже идём) |
| LangGraph | **Отдельный эпик** | Замена оркестратора; не hotfix |

## 1) Visual PH (Owner PC) — **done**

Повторный запуск (если нужно):

```powershell
cd "F:\Проекты MyWave\NEW2026\AI-Team"
powershell -ExecutionPolicy Bypass -File .\scripts\integration\run_ph_with_control.ps1
```

## 2) CURSOR_API_KEY (Owner PC) — **done**

Live smoke (после `git pull` Agents):

```powershell
cd "C:\ProjectMyWave\MyWave_AI_TEAM_Presets_v1_1"
$env:CURSOR_API_KEY = [Environment]::GetEnvironmentVariable("CURSOR_API_KEY","User")
& "F:\Проекты MyWave\NEW2026\AI-Team\AIProjectManager\.venv\Scripts\python.exe" scripts\smoke_cursor_sdk.py
```

Ожидание: `SDK_SMOKE_OK`. Shim `os.get_blocking` — в `app/runners/cursor_runner/win_os_shim.py` (smoke + `sdk_runner`).

## 3) CrewAI без fallback (RU — только если сознательно)

**Риск:** нет OpenAI/прокси → оркестрация падает вместо rule-based.

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
grep -q '^ORCHESTRATION_ALLOW_FALLBACK=' .env \
  && sed -i 's/^ORCHESTRATION_ALLOW_FALLBACK=.*/ORCHESTRATION_ALLOW_FALLBACK=false/' .env \
  || echo 'ORCHESTRATION_ALLOW_FALLBACK=false' >> .env

docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml --profile molt up -d

curl -sS -H "X-API-Key: $OWNER_API_KEY" http://127.0.0.1:8088/api/system/health \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['checks']['orchestration'])"
```

Откат:

```bash
sed -i 's/^ORCHESTRATION_ALLOW_FALLBACK=.*/ORCHESTRATION_ALLOW_FALLBACK=true/' .env
docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml --profile molt up -d
```

## 4) Что агенты **не** включают без нового отдельного GO

1. **Auto-merge** — никогда не мержит `main` автоматически.  
2. **Big-bang monorepo** — не склеиваем F:/C: «взрывом»; только ADR + MERGE_PLAN.  
3. **LangGraph** — новый runtime; сначала ADR + spike, не замена CrewAI за один PR.  
4. **Полный stream каждой реплики в TG** — оставляем `TELEGRAM_STAGE_NOTIFY` (границы этапов). Расширение = отдельный дизайн (лимиты TG).

## Итог

Боевой контур RU **готов**. Остаток — Owner PC (PH GUI + ключи) и опциональный флаг CrewAI.  
Опасные пункты требуют **нового явного GO по одному**, с ADR, не «всё сразу».
