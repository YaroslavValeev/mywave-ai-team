# Project Status

Snapshot date: **2026-07-23** (post backup-cron fix, `main` @ `b9cddd3`)

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

**Production governance is up** on `https://agm.mywavewake.ru` (`main` @ `b9cddd3`, health OK; backups working after PR #14).

- office-full + CrewAI path available on RU (with rule-based fallback)
- Telegram RU UI + approve buttons work
- Control API create / `auto_run` / approve proven (#4, #6, #7, #8 headless PH, **#11 DONE**)
- Three-layer HTTP contracts documented; monorepo merge **not** required for ops
- Open PRs: **none**

Still open (detail: [migration/POST_RECOVERY_REMAINING.md](migration/POST_RECOVERY_REMAINING.md)):

- Optional PH **visual** GUI one-click propose/apply on Owner PC
- Umbrella junction `services/agents_live` + local Agents→Molt E2E re-run
- Optional BotFather token rotation (only if token ever leaked)
- Optional umbrella Cursor SDK live key (`CURSOR_API_KEY`)

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

## Priority Recommendation

1. **Owner PC:** junction `agents_live` + local Molt E2E; optional PH visual GUI.
2. **Agents:** keep docs/tests green; do not touch prod without Owner.
3. **Defer:** big-bang monorepo, Molt on RU, CrewAI no-fallback guarantee, auto-merge.

## Discovery Plan Executed (this snapshot)

- Reviewed `docs/migration/INTEGRATION_THREE_LAYERS.md`, Step C/D, umbrella scripts
- Confirmed prod health + task #11 **DONE** + backups working (Owner report)
- Ran local pytest subset (owner console / gate / channel parity / e2e API / crewai config)
- Documented remaining work in `docs/migration/POST_RECOVERY_REMAINING.md`
- Added umbrella `scripts/integration/check_agents_pointer.ps1`
