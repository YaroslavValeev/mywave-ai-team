# AGENT_TUNING_WORKFLOW_PLAYBOOK — Phase 11.2

## Назначение

Playbook описывает agent-specific tuning workflow: от specialization signals до verification.

## Как появляется candidate

- **Источник**: specialization analytics (fallback hotspots, override-heavy, unstable execution lane)
- **Генерация**: `generate_tuning_candidates` или POST `/api/owner/tuning/proposals/generate`
- **Условие**: refinement signals с problem_pattern и recommended_change

## Когда candidate стоит review

- status = pending_review
- severity medium/high — приоритет
- Execution lane требует внимания (fallback rate, override count)

## Когда convert to proposal

- После accept (review)
- Candidate accepted → convert → refinement proposal (status accepted)
- Proposal идёт в patch apply workflow

## Как смотреть verification

- Post-apply: наблюдать fallback/override за verification_window_days
- Owner вручную: POST `/api/owner/tuning/{id}/verify` с outcome
- outcome: improved, unchanged, worse, insufficient_data

## Когда tuning признать успешным

- verification_outcome = improved
- baseline_signal снизился

## Когда возвращаться к registry refinement

- Verification = worse или unchanged при нескольких попытках
- Нужен manual review domain/specialization registry
- Tuning — execution-lane; refinement — general registry
