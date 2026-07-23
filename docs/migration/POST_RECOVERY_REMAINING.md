# Post-recovery remaining work

Snapshot: **2026-07-23** (Owner RU confirm @ `f7a1b03`, health ok, `WAIT_OWNER []`)  
Prod: `agm.mywavewake.ru` health **ok** (Owner `server_ops_check.sh`)  
Agents `main`: `f7a1b03` (PR #18)

Связано: [INTEGRATION_THREE_LAYERS.md](INTEGRATION_THREE_LAYERS.md), [PHASE_B_STEP_C_PH.md](PHASE_B_STEP_C_PH.md), [PHASE_B_STEP_D_MOLT.md](PHASE_B_STEP_D_MOLT.md)

---

## Closed since recovery

| Item | Status |
|------|--------|
| Mission **#11** (`MEDIA_OPS` / `marketing_plan`) | **DONE** (Owner approve) |
| Backup cron + `backup_postgres.sh` executable (PR #14) | **working on RU** (`mywave_ai_20260723.sql.gz`) |
| Reboot / alembic recovery (PR #12) | done |
| Owner console RU title pytest | fixed in PR #13 |
| Open GitHub PRs | **none** |
| Disk (C:/F: / RU `/`) | OK (RU ~66%) |
| Umbrella `services/agents_live` | **PASS** → `C:\ProjectMyWave\MyWave_AI_TEAM_Presets_v1_1` |
| Umbrella `packages/agents-http-client` | junction → C: package |
| Agents→Molt HTTP E2E (Owner PC) | **PASS** (`smoke_agents_molt_http_e2e.py`) |
| `AgentsControlClient.mark_merged` + criticality `MEDIUM` | **done** |
| Local pytest subset | green |

---

## Приоритеты остатка

### (A) Agents can finish now

Операционный Phase B / post-recovery **закрыт** для агентов. Дальше — только docs sync при новых Owner-логах; **не** approve / не rebuild RU без кода в `app/`.

### (B) Owner server commands (SSH RU)

Сейчас на RU уже **`f7a1b03`**, ops-check OK. Повторный pull не обязателен, пока нет нового PR.

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
git rev-parse --short HEAD   # f7a1b03
bash scripts/server_ops_check.sh
```

PR #18 (`packages/agents-http-client`) **не** в Docker app image → **rebuild не нужен**.  
Rebuild только если придёт PR с изменениями в `app/` / `Dockerfile` / compose.

Backup cron уже стоит. **Не нужно:** reboot, approve #11, `up -d --build`.

### (C) Owner PC only (optional)

1. Visual PH one-click: `run_ph_with_control.ps1` → propose/apply в GUI (headless + wiring + apply-path уже закрыты).
2. Опционально: BotFather ротация токена, если когда-либо светился в чате.
3. Опционально (umbrella): `pip install cursor-sdk` + `CURSOR_API_KEY` для реального Cursor executor (иначе `manual_hint`).

### (D) Defer

1. Big-bang monorepo / submodule поверх dirty F-копии Agents (`MyWave_AI_TEAM_Presets_v1_1` на F: @ stale branch — **не править**).
2. Deploy Molt на RU.
3. Полный русский Dashboard (бот уже RU).
4. Стриминг промежуточных реплик агентов в Telegram.
5. Provider-backed CrewAI «гарантированный» runtime без fallback (office-full уже работает с fallback).
6. Авто-merge в `main` (запрещено policy).
7. LangGraph orchestration (явно deferred).

---

## Доказательства аудита

| Проверка | Результат |
|----------|-----------|
| `git HEAD` (C: / RU) | `f7a1b03` |
| Prod health (Owner log) | `ok`; CrewAI `gpt-4.1-nano`; disk ~66%; nginx active |
| `WAIT_OWNER` | **[]** |
| Top tasks | #15–#11 **DONE** (incl. #11 `marketing_plan`) |
| Backups | cron OK + `20260722` / `20260723` |
| Umbrella junctions | `agents_live` + `agents-http-client` **PASS** |
| Agents→Molt HTTP E2E | **PASS** |
| HTTP client | `mark_merged` + criticality `MEDIUM` (PR #18) |
| PH visual GUI one-click | **optional Owner PC** |
| Open PRs | none |
