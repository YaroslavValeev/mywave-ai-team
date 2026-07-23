# Post-recovery remaining work

Snapshot: **2026-07-23** (Owner RU @ `c4397eb`, ops-check OK, CI green)  
Prod: `agm.mywavewake.ru` health **ok**  
Agents `main`: `c4397eb` (PR #20 channel-parity CI fix)

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

Сейчас на RU уже **`c4397eb`**, ops-check OK, CI на `main` **success**. Повторный pull не обязателен, пока нет нового PR.

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
git rev-parse --short HEAD   # c4397eb
bash scripts/server_ops_check.sh
```

PR #18 (HTTP client) и #20 (tests) **не** требуют Docker rebuild.  
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
| `git HEAD` (C: / RU) | `c4397eb` |
| CI `main` | **success** (PR #20) |
| Prod health | `ok`; disk ~66%; nginx active; backups OK |
| `WAIT_OWNER` | **[]** |
| Open PRs | none |
