# Post-recovery remaining work

Snapshot: **2026-07-23** (Owner RU ops @ `257b1c7` + junction/E2E + client parity)  
Prod: `agm.mywavewake.ru` health **ok** (Owner `server_ops_check.sh`)  
Agents `main`: `257b1c7` (PR #17)

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

### (A) Agents can finish now (без Owner GUI / без RU destructive)

1. Держать docs чеклисты в sync с этим файлом + Step C/D + `PROJECT-STATUS.md`.
2. Локальный pytest green после doc sync.
3. Не трогать прод без явного Owner; **не** approve чужие задачи.

### (B) Owner server commands (SSH RU)

После pull docs/code на `257b1c7` и новее. Docs-only — **без rebuild**. Code PR (client) — **нужен rebuild**:

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
git pull origin main
# если пришёл code-change в app/ или packages/:
docker compose -f docker-compose.yml -f docker-compose.server-full.yml up -d --build
bash scripts/server_ops_check.sh
```

Backup cron уже стоит — повторный `install_backup_cron.sh` **не нужен**.

**Не нужно сейчас:** reboot, approve #11, `docker compose … --build` только ради docs.

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
| `git HEAD` (C: Agents) | sync to latest `main` after this PR |
| Prod health (Owner log) | `ok`; CrewAI `gpt-4.1-nano`; disk ~66%; nginx active |
| `WAIT_OWNER` | **[]** |
| Task #11 | **DONE** |
| Backups | cron OK + `20260722` / `20260723` |
| Umbrella `services/agents_live` | **PASS** |
| Umbrella `packages/agents-http-client` | junction → C: package |
| Agents→Molt HTTP E2E | **PASS** |
| HTTP client | `mark_merged` + criticality default `MEDIUM` |
| PH visual GUI one-click | **optional Owner PC** |
| Локальный pytest | client + subset green |
