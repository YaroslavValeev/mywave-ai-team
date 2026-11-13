# TUNING_PATCH_PLAYBOOK — Phase 11.3

## Когда candidate patchable

- Тип `expand_specialization_keywords` и нет блокирующих флагов → после accept ожидается proposal с safe add profile.
- Уже сконвертирован: смотреть `GET /api/owner/tuning/{id}/patchability` — `apply_allowed` из Phase 10.7.

## Когда переводить в proposal

- После **accept** review tuning candidate.
- Затем `to-proposal` — сохраняется `source_tuning_candidate_id`.

## Когда применять patch

- Только если proposal **accepted** и dry-run/validate **ok** (существующий refinement patch UI или API).
- Не применять при `manual_only` классификации без ручной правки.

## Traceability

- Candidate → proposal → patch page → apply → baseline в outcome store → `evaluate_tuning_outcome`.

## Если patch не применён

- Outcome статус `not_patch_applied`; follow-up: завершить apply или закрыть candidate как manual.
