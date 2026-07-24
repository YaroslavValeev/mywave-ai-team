# ADR-006: LLM tier — local default, OpenAI via EU

## Status
Accepted (2026-07-24)

## Context
RU VPS (`62.113.42.227`) gets OpenAI `403 unsupported_country_region_territory`.
EU VPS (`72.56.99.214`) already hosts Telegram SOCKS; it can also host an
OpenAI-compatible LiteLLM proxy for cloud-quality CrewAI runs.

Owner wants:
- ordinary missions → small/local models (cost + no geo-block)
- hard missions → explicit OpenAI via EU (button or `#CLOUD` / `#OPENAI`)

## Decision
1. **Two tiers:** `local` | `cloud` (no third orchestrator).
2. **Default:** `LLM_TIER_DEFAULT=local` (or legacy single `OPENAI_BASE_URL` if tiers unset).
3. **Cloud path:** RU → `http://72.56.99.214:4000/v1` (LiteLLM) → OpenAI.
   Real `OPENAI_API_KEY` stays on EU; RU holds only `LITELLM_MASTER_KEY`.
4. **Owner control:** Telegram button `🧠 OpenAI (EU)` and tags `#CLOUD` / `#OPENAI`
   set `business_action_json.llm_tier=cloud` and re-run (or start) orchestration.
5. **SOCKS `:1080`** remains Telegram-only; LLM uses direct allowlisted `:4000`.

## Consequences
- CrewAI `_build_llm` resolves endpoint/model from active tier.
- Strict `ALLOW_FALLBACK=false` still applies per call; local+cloud both can fail.
- Rollback: set `LLM_TIER_DEFAULT=cloud` only after EU proxy is healthy, or keep
  `ALLOW_FALLBACK=true` with rule-based safety net.
