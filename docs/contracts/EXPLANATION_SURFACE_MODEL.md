# Explanation Surface Model (Phase 11.0)

## Описание

Где и как explanation появляется в UI / API / Telegram.

## Surfaces

| Surface | Short form | Expanded form | Default visible | Debug/detail only |
|---------|------------|---------------|-----------------|-------------------|
| task card | headline + 1–2 evidence | full rationale | headline, 2 evidence | full evidence_items, signals_used |
| project detail | headline | full rationale | headline, summary | evidence_items |
| portfolio block | headline per project | rationale list | headlines | full rationale |
| role view block | headline | rationale per item | headline | evidence |
| collaboration block | handoff reason | full rationale | reason, target_role | evidence_items |
| refinement proposal | reason + evidence_summary | full rationale | reason, recommended_change | source_signals |
| debug API | full rationale | — | — | всегда full |
| Telegram | compact text | — | headline + 2 evidence | — |

## Правила

- **Short form** — headline, до 2 evidence items, recommended_action (если есть).
- **Expanded form** — headline, summary, до 5 evidence items, confidence, recommended_action.
- **Default** — owner видит short form; expanded по клику или в detail view.
- **Debug** — signals_used, related_objects, generated_at только в API или debug mode.
