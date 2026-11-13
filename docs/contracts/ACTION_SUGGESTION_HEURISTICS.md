# Action Suggestion Heuristics (Phase 11.1)

## Rule-based explainable правила

### 1. Pending approval + reviewer bottleneck

- **Condition**: pending_count >= 2, handoff executor→owner
- **Signals**: collaboration_flows (approval_bottleneck), get_project_pending_approvals
- **Who**: owner
- **Action**: Разобрать approvals: /approvals или /owner
- **Why**: Backlog будет расти, поток замедлится
- **Suggestion type**: approval_resolution_needed

### 2. Repeated rework loop

- **Condition**: rework_cycles >= 2 или review_execution_loop hotspot
- **Signals**: rework_signal_summary, collaboration_flows
- **Who**: owner + executor (совместно)
- **Action**: Owner review, уточнение постановки; executor — учесть feedback
- **Why**: Риск повторного rework
- **Suggestion type**: rework_loop_break

### 3. Runtime escalation gap

- **Condition**: state == DEGRADED
- **Signals**: degraded_signal_summary
- **Who**: operator → owner
- **Action**: Проверить Molt, логи; эскалировать при необходимости
- **Why**: Риск срыва выполнения
- **Suggestion type**: runtime_escalation

### 4. Override-heavy project drift

- **Condition**: domain_drift_signal или domain_instability_signal
- **Signals**: project_domain_lifecycle
- **Who**: owner
- **Action**: Просмотреть /owner/portfolio, /domain_lifecycle; при необходимости — refinement backlog
- **Why**: Дрифт доменного профиля может требовать уточнения
- **Suggestion type**: project_focus_intervention

### 5. Unstable lifecycle + high attention project

- **Condition**: проект в focus list + (drift или instability)
- **Signals**: portfolio_focus_list, project_domain_lifecycle
- **Who**: owner
- **Action**: Заморозить активность по проекту, пересмотреть assumptions
- **Why**: Рекомендуется проверить доменный профиль перед продолжением
- **Suggestion type**: project_focus_intervention

### 6. Owner attention gap

- **Condition**: owner_attention_gap hotspot
- **Signals**: collaboration_flows
- **Who**: owner
- **Action**: Выделить внимание проекту: pending + rework/long-running
- **Why**: Проект может застрять
- **Suggestion type**: owner_attention_request

### 7. Handoff followup (task-level)

- **Condition**: task WAIT_OWNER или REWORK
- **Signals**: get_task_handoff_signals
- **Who**: target_role (owner для approval, executor для rework)
- **Action**: Закрыть handoff — approve/rework/clarify
- **Why**: Задача ждёт передачи
- **Suggestion type**: handoff_followup
