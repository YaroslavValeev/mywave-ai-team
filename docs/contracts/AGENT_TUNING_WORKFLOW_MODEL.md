# Agent Tuning Workflow Model (Phase 11.2)

## Lifecycle

1. **Specialization signals found** — analytics (fallback hotspots, override-heavy, unstable lane)
2. **Tuning candidate created** — из signals, с problem_pattern, recommended_change
3. **Candidate reviewed** — accept / reject / defer
4. **Candidate converted** — в refinement proposal (опционально)
5. **Patch applied** — через existing refinement patch workflow
6. **Verification window** — наблюдение post-apply (window_days)
7. **Result** — improved / unchanged / worse / insufficient_data

## Важно

- Tuning candidate ≠ immediate patch
- Tuning workflow — upstream слой над proposal workflow
- Verification — rule-based, explainable baseline (не магическая метрика)
- Conversion в proposal сохраняет trace (source_tuning_candidate_id)
