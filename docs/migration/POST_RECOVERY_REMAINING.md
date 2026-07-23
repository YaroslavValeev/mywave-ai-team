# Post-recovery remaining work

Snapshot: **2026-07-23** (post backup-cron fix)  
Prod: `agm.mywavewake.ru` health **ok**  
Agents `main`: `b9cddd3` (PR #14 backup script executable merged)

Связано: [INTEGRATION_THREE_LAYERS.md](INTEGRATION_THREE_LAYERS.md), [PHASE_B_STEP_C_PH.md](PHASE_B_STEP_C_PH.md), [PHASE_B_STEP_D_MOLT.md](PHASE_B_STEP_D_MOLT.md)

---

## Closed since recovery

| Item | Status |
|------|--------|
| Mission **#11** (`MEDIA_OPS` / `marketing_plan`) | **DONE** (Owner approve) |
| Backup cron + `backup_postgres.sh` executable (PR #14) | **working on RU** |
| Reboot / alembic recovery (PR #12) | done |
| Owner console RU title pytest | fixed in PR #13 |
| Open GitHub PRs | **none** |
| Disk (C:/F:) | OK (~148 GB / ~426 GB free) |

---

## Приоритеты остатка

### (A) Agents can finish now (без Owner GUI / без RU destructive)

1. Держать docs чеклисты в sync с этим файлом + Step C/D + `PROJECT-STATUS.md`.
2. Локальный pytest green (owner console / channel parity / e2e / gate) — прогон после doc sync.
3. Umbrella: `scripts/integration/check_agents_pointer.ps1` (статус) + при необходимости Owner запускает `link_agents_pointer.ps1` (см. C).
4. Не трогать прод без явного Owner; **не** approve чужие задачи.

### (B) Owner server commands (SSH RU)

1. Обычный ops после будущих PR: `git pull` + `docker compose … up -d --build` + `server_ops_check.sh`.
2. Backup cron уже стоит и работает — повторный `install_backup_cron.sh` **не нужен**, пока cron не сломается.

**Не нужно сейчас:** reboot, повторный GH merge recovery/backup PR, approve #11.

### (C) Owner PC only

1. Visual PH one-click: `run_ph_with_control.ps1` → propose/apply в GUI (headless + wiring уже закрыты).
2. Junction `services/agents_live` → `C:\ProjectMyWave\MyWave_AI_TEAM_Presets_v1_1` (`link_agents_pointer.ps1`). На F: сейчас **отсутствует** (есть обычная папка `services/agents`, не junction).
3. Локальный Agents→Molt HTTP E2E: `ensure_molt_up.ps1` + `smoke_agents_molt_http_e2e.py` (Molt **не** на RU).
4. Опционально: BotFather ротация токена, если когда-либо светился в чате.
5. Опционально (umbrella): `pip install cursor-sdk` + `CURSOR_API_KEY` для реального Cursor executor (иначе `manual_hint`).

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
| `git HEAD` | `b9cddd3` = `origin/main` |
| Open PRs | none |
| Prod health | `ok` (2026-07-23) |
| Task #11 | **DONE** |
| Backups | working (cron + executable fix) |
| Umbrella `services/agents_live` | **MISSING** |
| Umbrella `services/agents` | ordinary dir (not junction); F-copy dirty/stale |
| Integration scripts на F: | есть (`smoke_ph_*`, `smoke_agents_molt_http_e2e`, `link_agents_pointer`, `check_agents_pointer`, …) |
| PH headless GUI apply-path | **closed** (`smoke_ph_gui_apply_headless.py`, task #14 DONE) |
| PH visual GUI one-click | **optional Owner PC** (`run_ph_with_control.ps1`) |
| CrewAI | office-full + fallback OK; no-fallback guarantee deferred |
| Cursor SDK (umbrella) | code present; live key optional Owner PC |
| Disk C:/F: | OK |
| BotFather | optional only if token leaked |
| Локальный pytest subset | green (`test_owner_console`, `test_e2e_api_flow`, `test_channel_parity`, `test_gate_wait_owner`, `test_crewai_bridge_config`, `test_api_auto_run`) |
