# Decision Support to Action Relation (Phase 12.0)

## Связь intervention → action_center

| intervention_type | safe_action_key | action_center |
|-------------------|-----------------|---------------|
| approval | open_decision_queue | execute_action("open_decision_queue", "owner") |
| degraded | recheck_molt_health | execute_action("recheck_molt_health", "operator") |
| refinement_patch | — | /owner/refinement, apply_patch |
| tuning_patch | — | /owner/tuning, patchable |
| collaboration_execution | — | /owner/collaboration/executions |

## Visibility

- Если intervention.safe_action_available = true → показать "/do {safe_action_key}" сразу
- Если false → показать manual path (URL, описание)
- Не смешивать: один intervention = один primary action (safe или manual)

## Integration points

- owner_recommendations.get_next_actions → actions с suggested_safe_action
- intervention_planning._build_intervention_from_action → safe_action_key из action
- adaptive_decision_support → top_action с safe_action_key когда есть
