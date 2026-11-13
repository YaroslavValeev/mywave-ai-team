# Registry patch lifecycle (Phase 10.7)

## Этапы

1. **Proposal accepted** — refinement proposal имеет status=accepted (Phase 10.6).
2. **Patch candidate built** — build_patch_candidate(proposal_id) строит target_file, patch_type, proposed mutation, diff_summary; classify_patch_risk определяет safe/unsafe.
3. **Dry-run preview** — dry_run_patch(proposal_id) возвращает diff (old vs new content или текстовое описание), validation preview, apply_allowed; файлы не меняются.
4. **Validation** — validate_patch_candidate(proposal_id) проверяет YAML, структуру, дубликаты; возвращает validation_status и при необходимости validation_errors.
5. **Backup created** — перед apply создаётся snapshot целевого файла; backup_ref сохраняется.
6. **Apply** — apply_patch_candidate(proposal_id, actor) выполняет запись только для safe types и при validation ok; обновляет proposal status=applied; пишет audit registry_patch_applied.
7. **Post-apply verification** — verify_patch_after_apply(proposal_id) — опционально перечитывает файл и проверяет, что изменение присутствует.
8. **Rollback if needed** — rollback_patch(patch_id, actor) восстанавливает файл из backup_ref; только где rollback_supported; пишет audit registry_patch_rollback.

## Важно

- Accepted proposal не обязан автоматически переходить в apply; apply — отдельный явный шаг.
- Dry-run обязателен как минимум для информирования; в UI/API всегда доступен перед apply.
- Apply без успешной validation не выполняется.
- High-risk или unsupported patch type возвращает apply_allowed: false; реальное изменение — только вручную по экспорту.
