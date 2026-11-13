# Phase 11.8 — Acceptance

## Завершено

- [x] Расширенная SAFE_PATCH_MATRIX
- [x] Новые patch types: append_routing_keyword, add_alias, append_specialization_keyword, append_guardrail_note, update_summary_minor для domain_registry и specializations
- [x] refinement_exports: корректный target_file для domain_registry; expand_specialization_profile → append types
- [x] registry_patch_apply: _compute_new_domain_registry_content, _compute_append_specialization; apply для всех safe types
- [x] Validation: validate_domain_registry_structure для domain patches
- [x] Rollback: backup перед apply (как в 10.7)
- [x] patch_coverage.py: get_patch_coverage_summary (patchable vs manual-only, by_type)
- [x] Интеграция: get_pending_refinement_attention + patchable_count, manual_only_count, patchable_types

## Критерии

- adjust_routing_keywords и add_alias proposals получают apply_allowed при корректном target_key и append_value
- expand_specialization_profile → append_specialization_keyword/append_guardrail_note/update_summary_minor
- dry_run, validate, apply работают для domain_registry и specialization append типов
- patch coverage summary доступен

## Следующий этап

- Phase 11.9: project-domain evolution refinement
