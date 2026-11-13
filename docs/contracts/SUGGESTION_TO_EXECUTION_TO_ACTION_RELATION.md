# SUGGESTION_TO_EXECUTION_TO_ACTION_RELATION — Phase 11.4

1. **Signal** (hotspot, handoff) → collaboration flows.
2. **Rationale** → explanation assist (11.0).
3. **Suggestion** → action suggestions (11.1) + `suggestion_fingerprint`.
4. **Execution** → persistent record по fingerprint; статусы и audit.
5. **Safe action** → action center `execute_action` только при explicit trigger и валидном ключе.
6. **Closure** → `mark_collaboration_execution_closed` или acknowledged path.

Сущности **разделены**: suggestion ≠ execution ≠ action registry entry.
