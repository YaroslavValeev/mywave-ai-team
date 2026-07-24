# Project Status

Snapshot date: **2026-07-24** (Owner RU Molt GO + E2E + ops parity verified)

## What We Are Building

MyWave AI-TEAM is an internal operating system for owner-driven work across the MyWave ecosystem.

Its current shape is:

- Telegram bot for intake of `#TASK` requests from the owner
- FastAPI dashboard and control API for task visibility and orchestration
- AGM flow: `triage -> pipeline -> roundtable -> court`
- Artifact generation for handoffs and final reports
- Approval gate for critical execute actions
- MCP server and local runner for integration with coding agents and PR workflow
- Phase B three-layer glue: Personal_Helper / Agents Control API / Molt HTTP (local)

This is not a generic chatbot. It is a control plane for routing real MyWave tasks across multiple domains such as product development, media operations, events, game, infrastructure, sponsorship, R&D, and client ops.

## Current Stage

**Production governance is up** on `https://agm.mywavewake.ru` (Owner `server_ops_check` OK; disk ~67%).

- office-full + CrewAI on RU; **no-fallback** live (`ALLOW_FALLBACK=false`, `ENGINE=crewai`, 2026-07-24)
- Telegram RU UI + approve buttons work
- Control API create / `auto_run` / approve proven; **#11 DONE**; `WAIT_OWNER` empty
- Backups cron working (`20260723.sql.gz`)
- Umbrella `agents_live` + `agents-http-client` junctions; Agents→Molt HTTP E2E **PASS** on RU
- **Molt on RU:** `--profile molt` live (Owner GO); E2E task #16 **done**
- HTTP client: approve/rework/clarify/**merged**; default criticality `MEDIUM`

Closed on Owner PC (2026-07-24): PH visual (#19 DONE), `CURSOR_API_KEY` + `SDK_SMOKE_OK`.  
Closed on RU (2026-07-24): CrewAI no-fallback (ADR apply + env).

Still open (detail: [migration/POST_RECOVERY_REMAINING.md](migration/POST_RECOVERY_REMAINING.md)):

- Optional BotFather token rotation (only if token ever leaked)
- Policy-deferred (нужен отдельный GO): big-bang monorepo, full TG stream, auto-merge, LangGraph

## Product Scope Confirmed By Repo

- accept a task from Telegram, API, or MCP
- classify by domain, task type, criticality, and `PLAN` vs `EXECUTE`
- run structured workflow; persist task / audit / decisions / artifacts
- show progress in dashboard/API
- require owner approval for critical actions
- local PR loop without automatic merge to `main`

## What Is Already Working

### Control surfaces

- Telegram intake and owner callbacks (`app/bot/handlers.py`)
- Dashboard + REST Control API + MCP
- interface parity for approve/rework/clarify

### Persistence and lifecycle

- SQLAlchemy models + Alembic migrations
- end-to-end transitions to `WAIT_OWNER` or `DONE`
- retention + backup scripts + RU cron

### Safety and governance

- `OWNER_API_KEY` enforced
- approval checks for critical execute paths
- runner policy forbids auto-merge

### Operations

- Docker Postgres + nginx HTTPS on RU
- `GET /api/system/health`
- recovery path: alembic retry after reboot (PR #12)
- backup script executable for cron (PR #14)

### Phase B (Owner PC)

- `services/agents_live` → C:`main`
- Molt `:8765` + Agents→Molt HTTP E2E
- PH headless / wiring / apply-path smokes

## Priority Recommendation

1. **Owner RU:** `git pull` (ops parity PR); re-run `server_ops_check.sh`; verify health `checks.molt`.
2. **Owner PC (optional):** visual PH GUI one-click.
3. **Defer:** big-bang monorepo, CrewAI no-fallback guarantee, auto-merge.

## Discovery Plan Executed (this snapshot)

- Owner RU logs: health ok, backups present, `WAIT_OWNER []`, compose app+postgres up
- Created umbrella junction `agents_live` (Unicode-safe `New-Item`); `check_agents_pointer.ps1` PASS
- Re-ran Agents→Molt HTTP E2E → PASS
- Local pytest subset: 29 passed
- Updated remaining-work checklists
