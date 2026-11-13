# Agent Tuning Persistence Baseline (Phase 11.2)

## Где живут tuning candidates

- **Store**: `app/data/agent_tuning_candidates.json` (аналогично refinement_proposals.json)
- **Структура**: `{ "candidates": { "tc_xxx": {...} } }`
- **Env override**: `AGENT_TUNING_CANDIDATES_PATH`

## Review и verification status

- `status`: pending_review, accepted, rejected, converted, verified
- `reviewed_at`, `reviewer`, `review_notes`
- `proposal_id` — если конвертирован
- `verification_outcome`, `verification_at`, `verification_notes`

## Связь с refinement proposals

- Proposal может иметь `source_tuning_candidate_id`
- Tuning candidate при convert получает `proposal_id` и status=converted

## Audit

- События: tuning_candidate_created, tuning_candidate_reviewed, tuning_candidate_converted, tuning_candidate_verified
