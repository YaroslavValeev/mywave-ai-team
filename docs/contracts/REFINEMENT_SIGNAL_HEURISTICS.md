# Refinement signal heuristics (Phase 10.5)

Explainable правила для генерации refinement signals и backlog. Без opaque scoring.

## Domain override refinement signals

| Signal type | Condition | recommended_refinement_action | evidence_summary |
|-------------|-----------|-------------------------------|------------------|
| override_heavy_domain | count(domain_override) by domain_key >= 2 in window | review routing keywords / alias map for this domain | "N overrides to domain X in window" |
| override_heavy_project | count(domain_override) by project_key >= 2 in window | inspect override reasons for project X; consider domain preset | "N overrides in project X" |
| repeated_same_override_pattern | same (task or domain) with multiple override events | clarify task wording or domain preset | "Repeated overrides on same scope" |
| frequent_correction_a_to_b | many overrides from auto domain A to B | improve triage for A→B or add alias | "Frequent correction from A to B" (if derivable from payload) |

**Severity**: low/medium. **reason**: короткое текстовое объяснение (1–2 предложения).

## Specialization refinement signals

| Signal type | Condition | recommended_refinement_action | evidence_summary |
|-------------|-----------|-------------------------------|------------------|
| frequent_fallback_domain_step | fallback_count for (domain_key, workflow_step) >= 2 in window | add or expand specialization profile for domain X, step Y | "N fallbacks on domain X, step Y" |
| repeated_mismatch_same_spec | same specialization key often with mismatch (domain set but general) | add domain-specific profile or review domain selection | "Mismatch on spec Z" |
| unstable_execution_lane | high fallback_rate for domain or step | tighten registry or add profiles for domain/step | "Fallback rate X% for domain/step" |

**Severity**: low/medium. **reason**: explainable from counts and domain/step.

## Output shape (single signal)

- `signal_type`: string (e.g. override_heavy_domain, frequent_fallback_domain_step).
- `severity`: "low" | "medium".
- `reason`: human-readable 1–2 sentences.
- `recommended_refinement_action`: что сделать (add profile, review keywords, inspect manually).
- `evidence_summary`: короткая сводка (counts, domain_key, workflow_step, project_key).
- `domain_key`, `workflow_step`, `project_key`: опционально, если применимо.

Все сигналы строятся только на данных из override/specialization analytics (audit aggregates). Нет внешнего ML или скрытого ранжирования.
