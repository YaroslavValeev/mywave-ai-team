# Collaboration: signal → execution → outcome

Краткая цепочка Phase 10.9–11.5:

1. **Collaboration signal / hotspot** — `get_collaboration_hotspots`, handoff signals, project signals.
2. **Suggestion** — `collaboration_action_suggestions` (fingerprint, safe action).
3. **Execution** — `build_execution_from_suggestion` → `collaboration_executions.json`.
4. **Action** — `trigger_collaboration_execution` → `action_center` (если есть safe key).
5. **Closure** — `mark_collaboration_execution_closed` → baseline outcome snapshot.
6. **Outcome** — `evaluate_collaboration_execution_outcome` → сравнение baseline vs текущие сигналы.
7. **Follow-up** — флаг `followup_needed` + audit + рекомендации (`owner_recommendations`).
8. **Recommendation feedback** — сигналы `collaboration_execution_followup_signal`, `ineffective_collaboration_pattern_signal`, `effective_collaboration_pattern_signal`, `project_collaboration_needs_revisit` (с порогами).

Execution lifecycle и outcome **разделены**: outcome не меняет `execution_status`.
