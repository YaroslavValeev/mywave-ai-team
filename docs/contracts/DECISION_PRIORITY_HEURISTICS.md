# Decision Priority Heuristics (Phase 12.0)

Explainable приоритеты, без opaque scoring.

## Priority order (integer, lower = higher)

| Priority | Value | Когда |
|----------|-------|-------|
| high | 0 | approval pending, degraded, blocker, cross_layer_conflict |
| medium | 1 | rework, long_running, project_domain_attention, patchable_tuning, refinement_review |
| low | 2 | tuning_review, collaboration_followup, project_domain_drift, diversification |

## Action type → priority

- approval, degraded, cross_layer_alignment_conflict → high
- blocker, rework, long_running, project_domain_evolution_attention, patchable_tuning → medium
- refinement_review, tuning_review, collaboration_* → low (или medium при followup_needed)

## Safe action preference

Когда safe_action_available:
- поднимать в do_now при равенстве urgency
- явно показывать safe_action_key
- manual_path_required = false для этого item

Когда нет safe action:
- manual_path_required = true
- suggested_action = human-readable path (URL, command)
