# Project-domain Evolution to Intervention Relation (Phase 11.9)

## Связь signal → intervention

| refinement_class | owner_answer | intervention_type | safe_action |
|------------------|--------------|-------------------|-------------|
| weak_signal | — | — | — |
| transitional | review_recommended | refinement_review | /owner/project/{key}, /domain_lifecycle |
| normal_evolution | normal_evolution | — | — |
| attention_needed | owner_attention или refinement_or_tuning | project_domain_refinement | /owner/project/{key}, refinement backlog |

## Integration points

1. **intervention_planning.get_project_intervention_plan** — добавляет project_domain_evolution interventions если attention_needed
2. **intervention_planning.get_portfolio_intervention_plan** — приоритизирует project_domain_drift_requiring_intervention, project_domain_diversification_requiring_review
3. **owner_recommendations.get_next_actions** — project_domain_evolution_attention (refined)
4. **owner_recommendations.get_domain_aware_signals** — project_domain_evolution_signals (refinement_class, owner_answer)

## Refinement/tuning backlog link

- attention_needed + intervention_preferred = refinement_review → предложить создать refinement proposal (adjust_routing_keywords, add_alias, review_domain_mapping)
- attention_needed + specialization_fallback_hotspot → tuning_review
- linked_to_refinement_backlog: true если есть open refinement proposals по project_key или domain
