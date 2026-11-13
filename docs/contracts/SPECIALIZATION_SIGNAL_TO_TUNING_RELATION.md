# Specialization Signal → Tuning Relation (Phase 11.2)

## Путь

```
specialization signal (analytics)
    ↓
tuning candidate (agent-specific, execution-lane)
    ↓
review (accept / reject)
    ↓
conversion → refinement proposal (optional)
    ↓
patch apply (existing workflow)
    ↓
verification (improved / unchanged / worse)
    ↓
recommendation impact (owner sees tuning workload)
```

## Различие

- **Refinement backlog** — общий registry maintenance (domain, routing, aliases)
- **Tuning candidate** — agent/specialization execution lane improvement (profiles, fallback, guardrails)

Tuning — upstream слой; proposal — downstream. Tuning candidate может стать proposal.
