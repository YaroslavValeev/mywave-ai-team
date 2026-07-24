# Следующая волна — что можно / нельзя

Дата: 2026-07-24  
Контекст: RU/Molt/ops scope **закрыт**. Ниже — бывший «остаток».

## Матрица решений

| Пункт | Решение | Почему |
|-------|---------|--------|
| Visual PH GUI one-click | **Owner PC** (готовые скрипты) | Не сервер RU; нужен клик в desktop UI |
| `CURSOR_API_KEY` | **Owner PC** (секрет вручную) | Ключ только у Owner; runner на RU уже без Cursor CLI |
| CrewAI без fallback | **Опционально на RU** (флаг) | При падении LLM миссии падают hard; не default |
| Полный TG-stream каждой реплики | **Не сейчас** | Шум/лимиты TG/стоимость; уже есть stage-notify |
| Auto-merge в `main` | **Запрещено** | Runner policy + git safety: merge только Owner |
| Big-bang monorepo | **Запрещено взрывом** | Только по MERGE_PLAN инкрементально (уже идём) |
| LangGraph | **Отдельный эпик** | Замена оркестратора; не hotfix |

## 1) Visual PH (Owner PC, Windows)

```powershell
cd "F:\Проекты MyWave\NEW2026\AI-Team"

# env Control API (если нет — создаст из example и откроет notepad)
if (-not (Test-Path .\.env.agents-control)) {
  Copy-Item .\infra\env\.env.agents-control.example .\.env.agents-control
  notepad .\.env.agents-control
}
# В файле обязательно:
#   AGENTS_CONTROL_ENABLED=1
#   AGENTS_CONTROL_API_URL=https://agm.mywavewake.ru
#   AGENTS_API_KEY=<тот же что OWNER_API_KEY на RU>

powershell -ExecutionPolicy Bypass -File .\scripts\integration\run_ph_with_control.ps1
```

В UI: проект → **AI: обновить план** → **Применить предложения**.  
Проверка на RU после apply:

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
curl -sS -H "X-API-Key: $OWNER_API_KEY" https://agm.mywavewake.ru/api/tasks \
  | python3 -c "import sys,json; t=json.load(sys.stdin); print([(x['id'],x['status']) for x in t[:8]])"
```

## 2) CURSOR_API_KEY (Owner PC)

Нужен **только** для локального Cursor SDK / advanced runner на вашей машине.  
На RU Cursor CLI **не установлен** — это нормально; governance не зависит от ключа.

```powershell
# Пример (НЕ коммитьте ключ в git):
setx CURSOR_API_KEY "ваш_ключ_из_Cursor_dashboard"
# или в F:\Проекты MyWave\NEW2026\AI-Team\.env.local (если используете umbrella scripts)
```

Runner по канону: **PR создаёт, merge делает только Owner** (`docs/CURSOR-RUNNER.md`).

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
