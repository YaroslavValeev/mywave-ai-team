# Checkpoint 2026-11-23 (RU prod)

## Done this wave

### Owner productization
- A1–A2: `/owner`, projects, portfolio mounted
- A3: `/owner/domains|effectiveness|readiness` + APIs (PR #94)
- A4: Telegram `/domains` `/domain` `/route` (PR #95)
- Owner smoke with `X-API-Key`: all **200** on key owner routes

### KB
- Site project snippet dedupe + allowlist (TGK_MyWave_Site PR #125)
- Boundary contract Site KB ↔ Agents intake (AI-Team PR #96)

### Runtime ops (this session)
- `TELEGRAM_POLLING_ENABLED=true` (AI-Team token ≠ Site bot; polling started)
- `ORCHESTRATION_ENGINE=rule_based` (lite image; health **ok**)
- Deploy bind: always `docker compose -f docker-compose.yml -f docker-compose.server.yml`
- App: `127.0.0.1:8088`, Molt `:8765` ok, backups cron ok

## Health snapshot
- `/api/system/health` → **ok** (db/auth/gateway/telegram/orchestration/runner/molt)
- Runner note: Cursor CLI not in PATH on RU (expected; executor is Owner PC / SDK)
- Disk root ~83% (watch; light builder prune done)

## Cursor executor stance
- Code present: `app/runners/cursor_runner/*`, approve-gated `app/execution/service.py`
- Live SDK smoke: **Owner PC** with `CURSOR_API_KEY` (`scripts/smoke_cursor_sdk.py`)
- Do not install Cursor CLI on RU as default path
- Container import smoke: `cursor_runner` imports OK; no `CURSOR_API_KEY` in app container

## Next (safe order)
1. Owner TG E2E: `/domains` in AI-Team bot chat (manual)
2. Optional: inject `commit_sha` into release metadata on build
3. Optional: Wave 2 `knowledge_base/chat/projects/` fill
4. Defer: Federation, CrewAI full image, auto-merge, monorepo bang
