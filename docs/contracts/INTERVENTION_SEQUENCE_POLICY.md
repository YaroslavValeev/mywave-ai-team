# Intervention Sequence Policy (Phase 12.0)

## Preferred intervention rule

**do_now** = первый intervention в упорядоченном списке по правилам:

1. **Safe action first** — если есть intervention с safe_action_available=true и urgency high/medium, он в do_now
2. **Urgency order** — high > medium > low
3. **Conflict/degraded first** — cross_layer_alignment_conflict, degraded
4. **Approval bottleneck** — approval, open_decision_queue
5. **Project/portfolio** — project_intervention, project_domain_refinement
6. **Refinement/tuning** — refinement_review, tuning_review, patchable
7. **Defer** — остальное в defer

## do_next

Второй по приоритету (не совпадает с do_now по типу, если возможно).

## Fallback

Остальные — defer. Не показывать более 5 в компактном виде.

## Merge similar

- Похожие conflict_type — один bundle
- Одинаковый action_type по scope — не дублировать
