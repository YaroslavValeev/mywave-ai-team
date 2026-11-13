# Phase 10.7 — Controlled registry patch application and safe tuning (Acceptance)

## Что считается завершённым

- **Patch model** — описана в docs/contracts/REGISTRY_PATCH_MODEL.md (patch_id, proposal_id, target_layer, target_file, patch_type, patch_status, diff_summary, validation_status, backup_ref, applied_at, applied_by, rollback_supported).
- **Safe patch policy** — docs/contracts/SAFE_PATCH_POLICY.md: что можно/нельзя применять автоматически, risk levels, requires accepted/dry-run/backup.
- **Patch lifecycle** — docs/contracts/REGISTRY_PATCH_LIFECYCLE.md: proposal accepted → patch candidate → dry-run → validation → backup → apply → post-apply verify → rollback.
- **Builder/apply/validation/backups** — реализованы: registry_patch_builder.py, registry_patch_apply.py, registry_validation.py, registry_backups.py.
- **Audit** — события registry_patch_built, registry_patch_dry_run, registry_patch_validated, registry_patch_applied, registry_patch_rollback, registry_patch_failed (через существующий audit).
- **Web entrypoints** — /owner/refinement/proposal/{id}/patch (страница), GET/POST API: .../patch, .../patch/dry-run, .../patch/apply, .../patch/validate, .../patch/{patch_id}/rollback.
- **Telegram** — /patch_refinement, /dry_run_patch, /apply_patch (owner-only).
- **Presenters** — registry_patch_presenters.py: present_patch_candidate, present_patch_dry_run, present_patch_validation, present_patch_apply_result, present_patch_error, форматы для Telegram и web.
- **Playbooks и relation** — REGISTRY_PATCH_PLAYBOOK.md, SAFE_PATCH_APPLY_PLAYBOOK.md, PROPOSAL_PATCH_APPLY_RELATION.md.
- **Recommendations** — owner_recommendations: get_pending_refinement_attention расширена полями safe_patch_candidates_count, high_risk_not_auto_applicable_count, failed_patch_validation_count, patch_message; в get_next_actions добавлены refinement_patch_apply и refinement_patch_validation при наличии.
- **ADR** — ADR-041-controlled-registry-patch-application-and-safe-tuning.md.
- **Тесты** — покрытие сценариев A–I (build candidate, safe policy, dry-run, apply safe, block high-risk, audit, routes/commands, recommendations, регрессия 10.6).

## Что остаётся следующим этапом

- Deeper project-domain lifecycle.
- Collaboration flows.
- Explanation assist.
- Semi-automated tuning expansion (например append_routing_keyword/add_alias к domain_registry с file-backed apply).
- Agent-specific tuning workflows.
