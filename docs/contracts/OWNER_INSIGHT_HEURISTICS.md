# Owner insight heuristics (Phase 9.2)

- **Repeated rework:** task считается сигналом, если `rework_cycles >= 2` или длительно находится в `REWORK`.
- **Long-running:**  
  - waiting-owner состояния (`WAIT_OWNER`, `APPROVED_WAIT_MERGE`) дольше 24ч;  
  - runtime состояния (`IN_PIPELINE`, `IN_ROUNDTABLE`, `IN_COURT`) без прогресса дольше 6ч.
- **Degraded frequency signal:** события из `audit_events`, где `event_type` содержит `error`, `degraded` или `rollback`, за окно 7 дней + текущий `state` из status summary.
- **Time windows:** weekly digest = 7 дней; completed recently = 7 дней.
- **Ограничения:** эвристики explainable, не претендуют на BI-точность; не заменяют детальный инцидент-анализ.
