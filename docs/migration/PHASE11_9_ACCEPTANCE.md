# Phase 11.9 — Acceptance

## Deliverables

- [x] ADR-053
- [x] Contracts: PROJECT_DOMAIN_EVOLUTION_REFINEMENT_MODEL, DRIFT_HEURISTICS, DIVERSIFICATION_HEURISTICS, EVOLUTION_TO_INTERVENTION_RELATION
- [x] project_domain_evolution_refinement.py: get_project_domain_evolution_refinement, list_project_domain_attention_items, get_drift_requiring_intervention, get_diversification_requiring_review, get_project_domain_transition_summary
- [x] intervention_planning: project-domain evolution signals
- [x] owner_recommendations: project_domain_evolution_attention
- [x] Surfaces: project, portfolio, Telegram — evolution refinement answer
- [x] project_domain_evolution_presenters.py
- [x] Tests: shape, healthy vs harmful, attention items, visibility, intervention linkage

## Критерии

- healthy diversification не лезет в intervention
- harmful drift флажится для intervention
- unstable domain mix → attention item
- owner видит краткий ответ: нормально / review / refinement / owner attention
- lifecycle и patch features не сломаны
