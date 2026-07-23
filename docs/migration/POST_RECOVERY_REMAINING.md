# Post-recovery remaining work

Snapshot: **2026-07-23**  
Prod: `agm.mywavewake.ru` health **ok**  
Agents `main`: `51768fd` (PR #12 reboot/alembic recovery merged)

Связано: [INTEGRATION_THREE_LAYERS.md](INTEGRATION_THREE_LAYERS.md), [PHASE_B_STEP_C_PH.md](PHASE_B_STEP_C_PH.md), [PHASE_B_STEP_D_MOLT.md](PHASE_B_STEP_D_MOLT.md)

---

## Live gate: Mission #11 (WAIT_OWNER)

| Поле | Значение |
|------|----------|
| task_id | **11** |
| status | `WAIT_OWNER` |
| domain | `MEDIA_OPS` |
| task_type | `marketing_plan` |
| смысл | Маркетинговый план 0 ₽ — нужен **owner approve**, не auto-close |

### Как утвердить (Owner)

**A. Telegram (предпочтительно)**  
В сообщении по миссии #11 нажмите **Утвердить** (callback `a:11`).  
Текстовой команды `/approve` в боте **нет** — только кнопки + Dashboard/API.

**B. Dashboard**  
`https://agm.mywavewake.ru/mission/11` или `/tasks/11` → **Утвердить**  
(или cookie/PIN вход, если настроен).

**C. API / smoke (с сервера или локально с ключом)**

```bash
cd /opt/mywave/ai-team && set -a; source .env; set +a
python3 scripts/smoke_agents_control.py --approve 11 --note "owner ok marketing plan"
# эквивалент:
curl -sS -X POST "https://agm.mywavewake.ru/api/tasks/11/approve" \
  -H "X-API-Key: $OWNER_API_KEY" -H "Content-Type: application/json" \
  -d '{"note":"owner ok"}'
```

Ожидание после approve: статус **DONE** (или `APPROVED_WAIT_MERGE`, если есть PR-gate).

---

## Приоритеты остатка

### (A) Agents can finish now (без Owner GUI / без RU destructive)

1. Держать docs чеклисты в sync (этот файл + Step C/D).
2. Локальный pytest: `test_owner_console` (RU title) — фикс в репо.
3. Umbrella: подготовить/проверить `link_agents_pointer.ps1` → `services/agents_live` (скрипт есть; junction на диске F: сейчас **отсутствует**).
4. Не трогать прод без явного Owner; approve #11 — только по решению Owner.

### (B) Owner server commands (SSH RU)

1. Опционально: `bash scripts/install_backup_cron.sh` (если cron ещё не стоит).
2. Обычный ops после будущих PR: `git pull` + `docker compose … up -d --build` + `server_ops_check.sh`.
3. Approve #11 через API/smoke **если** Owner согласен с планом, но не хочет жать кнопку в TG.

**Не нужно сейчас:** reboot (уже сделан), повторный GH merge recovery PR (уже в `main`).

### (C) Owner PC only

1. Visual PH: `run_ph_with_control.ps1` → propose/apply в GUI (headless уже закрыт).
2. Junction `services/agents_live` → `C:\ProjectMyWave\MyWave_AI_TEAM_Presets_v1_1`.
3. Локальный Agents→Molt HTTP stack: `ensure_molt_up.ps1` + `smoke_agents_molt_http_e2e.py` (Molt **не** на RU).
4. Опционально: BotFather ротация токена, если когда-либо светился в чате.

### (D) Defer

1. Big-bang monorepo / submodule поверх dirty F-копии Agents.
2. Deploy Molt на RU.
3. Полный русский Dashboard (бот уже RU).
4. Стриминг промежуточных реплик агентов в Telegram.
5. Provider-backed CrewAI «гарантированный» runtime без fallback (office-full уже работает с fallback).
6. Авто-merge в `main` (запрещено policy).

---

## Доказательства аудита

| Проверка | Результат |
|----------|-----------|
| `git HEAD` | `51768fd` = `origin/main` |
| Prod health | `ok` (2026-07-23) |
| Task #11 | `WAIT_OWNER` / `MEDIA_OPS` / `marketing_plan` |
| Umbrella `services/agents_live` | **MISSING** |
| Integration scripts на F: | есть (`smoke_ph_*`, `smoke_agents_molt_http_e2e`, `link_agents_pointer`, …) |
| Локальный pytest subset | 19 passed; 1 fail → RU title в `/missions` (исправлено в тесте) |
