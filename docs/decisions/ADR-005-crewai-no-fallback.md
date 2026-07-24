# ADR-005: CrewAI no-fallback on RU

## Status

Accepted and **applied on RU** (Owner GO + env 2026-07-24):
`ORCHESTRATION_ALLOW_FALLBACK=false`, `ORCHESTRATION_ENGINE=crewai`, health orchestration ok.

## Context

RU office-full runs CrewAI (`gpt-4.1-nano`) with default
`ORCHESTRATION_ALLOW_FALLBACK=true`. On LLM/credential failure the stack
silently continues via rule-based triage/pipeline.

Owner requested **strict** CrewAI: no silent rule-based fallback.

## Decision

1. Set on RU `.env`:
   - `ORCHESTRATION_ALLOW_FALLBACK=false`
   - keep `ORCHESTRATION_ENGINE=auto` (or set `crewai`) — both are strict when fallback is off
2. Code: `crewai_strict_required()` treats `engine=auto|crewai` + `allow_fallback=false`
   as hard-fail when CrewAI returns empty (triage + pipeline).
3. Health: missing CrewAI package / LLM credentials → `checks.orchestration` = **error**
   (not warn) when fallback is off.

## Consequences

- Pros: real LLM path is mandatory; failures are visible; no silent downgrade.
- Cons: OpenAI/proxy outage → tasks fail until rollback or LLM restored.
- Rollback: `ORCHESTRATION_ALLOW_FALLBACK=true` + recreate `app` container.

## Non-goals

- Does not change Telegram stage notify, Molt, or Cursor SDK.
- Does not enable auto-merge or LangGraph.
