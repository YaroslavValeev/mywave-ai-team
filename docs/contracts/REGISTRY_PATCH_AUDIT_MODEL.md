# Registry patch audit model (Phase 10.7)

## События

- **registry_patch_built** — построен patch candidate. Payload: proposal_id, patch_type, target_file, risk_level.
- **registry_patch_dry_run** — выполнен dry-run. Payload: proposal_id, diff_summary, validation_preview, apply_allowed.
- **registry_patch_validated** — пройдена валидация. Payload: proposal_id, validation_status, validation_errors (если есть).
- **registry_patch_applied** — патч применён к файлу. Payload: proposal_id, patch_id, target_file, backup_ref, patch_type, actor.
- **registry_patch_rollback** — выполнен откат. Payload: patch_id, target_file, actor.
- **registry_patch_failed** — apply или validation не удались. Payload: proposal_id, reason, validation_errors (если есть).

Используется существующий механизм log_audit(repo, event_type, task_id=None, payload=...).
