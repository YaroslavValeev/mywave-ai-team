# Signal → intervention relation (Phase 11.7)

Цепочка (все read-only, intervention не создаёт новые сущности):

1. **Signal** — hotspot, outcome, recommendation, cross-layer conflict.
2. **Rationale** — explanation assist, why_now.
3. **Decision support** — options, preferred, risk (Phase 11.1).
4. **Intervention plan** — do_now, do_next, defer, preferred_sequence (Phase 11.7).
5. **Safe action / manual path** — action_center key или ручной путь.
6. **Expected effect** — что ожидается после выполнения.

Intervention **связывает** signal → rationale → decision support → action, но не подменяет execution/suggestion/action. Execution создаётся через collaboration_action_suggestions + build_execution_from_suggestion; action выполняется через action_center.execute_action.
