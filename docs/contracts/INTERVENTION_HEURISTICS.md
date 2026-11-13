# Intervention heuristics (Phase 11.7)

Детерминированные правила в `app/services/intervention_planning.py`.

## Порядок приоритетов (почему preferred order)

| Ситуация | Preferred order | Why |
|----------|-----------------|-----|
| collaboration improved + tuning worse | 1) tuning review, 2) collaboration follow-up if needed | Сначала стабилизировать tuning lane, потом collaboration |
| repeated follow-up + no effective collaboration | owner attention intervention | Нужен ручной разбор координации |
| patchable tuning + weak lane | patch path preferred | Safe path доступен |
| project drifting + override-heavy + refinement backlog | project review bundle | Связанные проектные риски |
| runtime escalation + owner attention gap | 1) operator-first (recheck_molt_health), 2) owner digest | Сначала операционный check |

## Safe action mapping

- **open_decision_queue** — approval bottleneck
- **recheck_molt_health** — runtime degraded
- **apply_patch** (через refinement) — patchable tuning
- **trigger_collaboration_execution** — collaboration execution available

Если safe action доступен — он в preferred path. Иначе — manual_path_required=true.

## Когда manual path required

- Нет зарегистрированного safe action для данной ситуации
- Требуется ручной review / clarify
- Intervention вне action_center (например, пересмотр приоритетов проекта)
