# Collaboration outcome heuristics (explainable rules)

Все правила **детерминированы** в коде `app/services/collaboration_outcomes.py`. Ниже — каноническое описание.

## Общий шаг
1. При **закрытии** execution фиксируется `baseline_signal_bundle` (снимок глобальных и проектных сигналов).
2. При **evaluate** снимается новый bundle и сравнивается **primary metric** в зависимости от `execution_type`.

## Сравниваемые сигналы (before / after)
| Тип execution | Primary metric | Сигналы |
|---------------|----------------|---------|
| `request_decision_resolution` | `global_pending` или `project_pending` | `get_awaiting_decisions_summary` / проект из `list_projects` |
| `escalate_runtime_issue` | `runtime_pressure` | `degraded` (state DEGRADED) + `global_blockers` |
| `request_owner_attention` | `project_attention` или `global_pending` | pending+rework+long_running по проекту |
| `request_review` | `global_rework` или `project_rework` | rework count |
| `mark_handoff_followup` | `handoff_pressure` | pending + rework |
| `acknowledge_collaboration_gap` | `collab_gap_pressure` | pending + rework |

## Measurement window
- Параметр `window_days` в evaluate влияет на **объяснение** и порог уверенности: при `window_days < 3` и `unchanged` результат понижается до `insufficient_data`.

## Минимальное правило доказательности
- Если нет `baseline_signal_bundle` → `insufficient_data`.
- Если execution не `closed` → `insufficient_data`.
- Если `cancelled` → не оцениваем.
- Если для project-scoped метрики проект не найден в `list_projects` → NaN → `insufficient_data`.

## Follow-up condition
- `followup_needed=true` при: `insufficient_data` (кроме отмены), `unchanged`, `worse`, коротком окне.
- `followup_needed=false` при уверенном `improved`.

## Интерпретация по типам (карта на метрики)
- **Approval bottleneck** execution: эффективен, если pending (глобально или по проекту) **снизился**.
- **Runtime escalation**: эффективен, если `runtime_pressure` снизился (снят degraded и/или blockers).
- **Review loop**: эффективен, если rework-сигнал **снизился**.
- **Owner attention (проект)**: эффективен, если сумма project pending/rework/long_running **снизилась**.
- **Unchanged**: метрика в пределах epsilon → follow-up.
- **Worse**: метрика выросла → ineffective + follow-up.
