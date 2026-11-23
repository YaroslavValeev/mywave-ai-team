# ADR-040: Owner Decision Pack for BUSINESS / finance-business tasks

## Status
Accepted — 2026-11-24

## Context
Rule-based court reports for BUSINESS/revenue tasks returned process scaffolding
(«миссию подготовили», WAIT_OWNER) without hypotheses, specialist summaries,
simulations, or success probabilities. Owner expects a decision pack.

## Decision
For `detect_business_plan_intent` / BUSINESS / `revenue_execution`:

1. Pipeline handoffs (PS/PM/FIN/DATA/LEGAL/CONTENT/RC) attach role-specific
   summaries, hypothesis fragments, and simulations via `business_plan_intent.py`.
2. Court `final_report.md` includes section **«Пакет решения владельца»**:
   hypotheses + how to test, simulations, specialist summaries, conclusion,
   probability table, owner next steps.
3. Telegram `summary` appends short P(success) hint pointing to full report.
4. Probabilities are **transparent heuristics** (not ML), labeled with basis.

## Consequences
- Owner gets substantive PLAN output without CrewAI/full image.
- Numbers remain assumptions until RGUFK/price confirmed; pack states that.
- Parallel pattern to `marketing_intent` / `content_intent`.

## Out of scope
- Live spreadsheet export
- Auto-merge of external md business plans into artifacts
- Changing Telegram edge architecture
