# Safe patch apply playbook (Phase 10.7)

## Последовательность действий

1. **Proposal accepted** — убедиться, что refinement proposal принят (review accept).
2. **Patch candidate** — GET `/api/owner/refinement/proposal/{id}/patch` или страница `/owner/refinement/proposal/{id}/patch`: смотреть target_file, patch_type, risk_level, apply_allowed.
3. **Dry-run** — POST `.../patch/dry-run`: проверить diff_summary и validation_preview; при apply_allowed=true можно переходить к apply.
4. **Validate** — POST `.../patch/validate`: при validation_status=ok можно применять.
5. **Apply** — POST `.../patch/apply` с body `{ "actor": "web" }` (или Telegram: `/apply_patch <id>`). Перед записью создаётся backup; при успехе proposal переводится в applied.
6. **Rollback** — при необходимости POST `/api/owner/refinement/patch/{patch_id}/rollback` (только для зарегистрированных патчей).

## Ограничения

- Apply без успешной validation не выполняется.
- High-risk и не-safe типы возвращают ошибку «manual apply required».
- Реализованный автоматический apply только для типа `add_specialization_profile` к `specializations.yaml`; domain_registry/aliases — пока через export и ручное изменение.

## Telegram

- `/patch_refinement <proposal_id>` — показать patch candidate.
- `/dry_run_patch <proposal_id>` — dry-run.
- `/apply_patch <proposal_id>` — применить (owner-only).
