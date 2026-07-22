# Project Status

Snapshot date: 2026-03-31

## What We Are Building

MyWave AI-TEAM is an internal operating system for owner-driven work across the MyWave ecosystem.

Its current shape is:

- Telegram bot for intake of `#TASK` requests from the owner
- FastAPI dashboard and control API for task visibility and orchestration
- AGM flow: `triage -> pipeline -> roundtable -> court`
- Artifact generation for handoffs and final reports
- Approval gate for critical execute actions
- MCP server and local runner for integration with coding agents and PR workflow

This is not a generic chatbot. It is a control plane for routing real MyWave tasks across multiple domains such as product development, media operations, events, game, infrastructure, sponsorship, R&D, and client ops.

## Product Scope Confirmed By Repo

The repo and docs describe one system around these responsibilities:

- accept a task from Telegram, API, or MCP
- classify it by domain, task type, criticality, and `PLAN` vs `EXECUTE`
- run a structured workflow
- persist task state, audit, decisions, and artifacts
- show progress in dashboard/API
- require owner approval for critical actions
- support a local PR loop without allowing automatic merge to `main`

## Current Stage

Current stage: MVP plus hardening with interface parity, richer orchestration artifacts, and optional CrewAI bridge. Still not full autonomous production execution.

The repository is beyond prototype level because it already has:

- working bot, dashboard, API, MCP server, database models, migrations, Docker setup
- access control and startup fail-fast around `OWNER_API_KEY`
- audit trail and decision logging
- tests that pass locally
- explicit production constraints around manual owner approval and manual merge
- **Live Telegram E2E (CANONICAL SCENARIO v1):** documented in `docs/CANONICAL-SCENARIO-V1.md` — task_id **8**, 2026-04-12, office-lite, full orchestration path to **WAIT_OWNER** with owner buttons (approve path optional follow-up in same doc)

At the same time, the core intelligence/orchestration layer is still mostly deterministic and not yet production-backed by a fully configured CrewAI runtime:

- `app/orchestrator/triage.py` is keyword-based
- `app/orchestrator/pipeline.py` now generates contextual handoffs and can consume optional CrewAI outputs
- `app/orchestrator/roundtable.py` now derives risks from gate, criticality, and pipeline evidence
- `app/orchestrator/crewai_bridge.py` is wired as an optional bridge, but still depends on provider/runtime setup
- `app/gateway` and `app/runners/cursor_runner` implement the intended contract (capabilities YAML, secret resolution, real `cursor` subprocess, env merge with gateway); further work is mostly product/runtime depth (CrewAI, richer runner modes), not wiring stubs

This means the project is at the stage where the control plane exists, but the real execution intelligence is still being swapped in.

## What Is Already Working

### 1. Control surfaces

- Telegram intake and owner callbacks in `app/bot/handlers.py`
- Dashboard pages in `app/dashboard/app.py` and templates
- REST API in `app/dashboard/api_router.py`
- MCP tool surface in `app/mcp_server/tools.py` and `app/mcp_server/executor.py`
- interface parity for approve/rework/clarify and artifact viewing

### 2. Persistence and lifecycle

- SQLAlchemy models for tasks, audit events, decisions, handoffs
- migrations in `app/storage/migrations`
- end-to-end task state transitions up to `WAIT_OWNER` or `DONE`
- retention cleanup script for old tasks and orphan audit events

### 3. Safety and governance

- `OWNER_API_KEY` enforced at startup and on API routes
- redaction and secret scrubbing
- approval checks for critical execute paths
- runner policy explicitly forbids auto-merge
- Telegram retry/backoff for transient send failures

### 4. Operations

- Docker and Postgres deployment path
- Caddy-based production layout documented
- local SQLite fallback path
- `GET /api/system/health` for database, auth, Telegram, orchestration, runner readiness

## What Is Missing Or Incomplete

The largest gaps are not infrastructure anymore. They are feature-completeness and real execution depth.

### Remaining execution gap

- CrewAI bridge is optional, not yet a guaranteed production runtime
- no provider-specific CrewAI deployment/profile config is committed
- orchestration still falls back to deterministic logic by default

### Remaining workflow gap

- no full Telegram plus Runner plus manual merge automated proof yet
- health/failure reporting for external integrations is still thin

## Evidence From The Current Snapshot

- README labels the project as `MVP v0` with later `v0.2` and `v0.2.1` hardening layers
- recent git history is dominated by hardening, CI, audit, and security work rather than new orchestration capability
- local SQLite snapshot currently contains 2 tasks, both in `NEW`, which suggests the local DB is not an actively used production dataset
- test suite currently passes locally with `python -m pytest -q`
- retention cleanup script exists at `scripts/run_retention.py`
- system health endpoint exists at `/api/system/health`
- E2E API flow is covered by `tests/test_e2e_api_flow.py`

## Recommended Plan

### Phase 1. Finish control-plane parity

Goal: make all interfaces consistent before deepening autonomy.

- add API endpoints for approve, rework, clarify
- expose the same actions in Dashboard
- add `tasks_list` to MCP
- make artifact navigation easier from dashboard detail page

Why first:

- small surface area
- immediate owner value
- reduces operational friction without changing core architecture

Status: completed for MVP.

### Phase 2. Replace orchestration stubs with real execution

Goal: turn the AGM flow from a shell into a real multi-agent pipeline.

- define the boundary between rule-based routing and CrewAI execution
- implement `crewai_bridge.py`
- make pipeline handoffs contain real structured outputs
- make roundtable reviewers depend on actual pipeline evidence

Why second:

- this is the main product delta
- the current repo is ready for this layer structurally, but not behaviorally

Status: completed for MVP.

### Phase 3. Close operational reliability gaps

Goal: reduce manual fragility in day-to-day use.

- add retention job
- add Telegram retry/backoff
- add health and failure reporting around external integrations
- verify deploy and backup flow against real production runbook

Status: partially completed.

### Phase 4. Run one true end-to-end owner scenario

Goal: validate the whole system as a workflow, not just as separate modules.

- create task through Telegram or MCP
- run pipeline
- attach PR through runner
- approve through chosen interface
- confirm manual merge and close task
- record final evidence in docs

Status: API E2E path exists, including manual merge confirmation; Telegram/Runner/manual merge proof remains.

## Priority Recommendation

The best next move is provider-backed CrewAI runtime plus external integration health reporting.

Reason:

- control-plane parity is already in place
- orchestration artifacts are now good enough to validate a real model-backed bridge
- the biggest remaining risk is runtime reliability, not missing CRUD surfaces

## Discovery Plan Executed

This snapshot was produced by:

- reviewing README and project docs
- inspecting core modules under `app/`
- inspecting tests and current repo history
- checking the local SQLite task state
- running the test suite successfully
