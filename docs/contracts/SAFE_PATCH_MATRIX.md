# Safe Patch Matrix (Phase 11.8)

## Patch types и target files

| patch_type | target_file | target_layer | операция | rollback |
|------------|-------------|--------------|----------|----------|
| add_specialization_profile | specializations.yaml | specializations | добавить новую запись | ✓ backup |
| append_routing_keyword | domain_registry.yaml | domain_registry | append в routing_keywords домена | ✓ backup |
| append_typical_request | domain_registry.yaml | domain_registry | append в typical_requests домена | ✓ backup |
| add_alias | domain_registry.yaml | domain_registry | append в aliases домена | ✓ backup |
| append_specialization_keyword | specializations.yaml | specializations | append в selection_keywords профиля | ✓ backup |
| append_guardrail_note | specializations.yaml | specializations | append в guardrails профиля | ✓ backup |
| update_summary_minor | specializations.yaml | specializations | обновить summary (replace) | ✓ backup |

## Proposal type → patch type

| proposal_type | patch_type | примечание |
|---------------|------------|------------|
| add_specialization_profile | add_specialization_profile | новая запись |
| expand_specialization_profile | append_specialization_keyword \| append_guardrail_note \| update_summary_minor | по recommended_change |
| adjust_routing_keywords | append_routing_keyword | append keywords |
| add_alias | add_alias | append alias |

## Manual-only (не patchable)

- review_domain_mapping
- tighten_fallback_rule
- Любое изменение с удалением/переименованием
- target_file не разрешён (or, множественный выбор)

## Validation

- domain_registry: validate_domain_registry_structure, no duplicate in list
- specializations: validate_specializations_structure, check_duplicate_specialization_key (для add)
