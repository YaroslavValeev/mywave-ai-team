# COLLABORATION_FLOWS_PLAYBOOK — Phase 10.9

## Назначение

Playbook описывает, как читать и использовать collaboration signals в системе. Collaboration layer — четвёртый слой поверх role / domain / project intelligence: он показывает, как роли должны взаимодействовать, где handoff застревает, и какие cross-role действия рекомендованы.

## Как читать collaboration signals

### 1. Handoff signals

- **source_role** → **target_role**: кто держит работу, кому передать.
- **handoff_type**: `executor_to_owner`, `owner_to_executor`, `operator_to_owner` и т.п.
- **handoff_readiness**: `ready`, `partial`, `blocked` — насколько handoff готов.
- **handoff_blockers**: что мешает передаче.

### 2. Collaboration hotspots

- **approval_bottleneck** — много pending approvals, owner перегружен.
- **review_execution_loop** — повторный rework, нужна координация owner–executor.
- **runtime_escalation_gap** — degraded/blockers, нужна эскалация operator → owner.
- **owner_attention_gap** — проект с pending + rework/long-running, owner должен уделить внимание.
- **domain_handoff_mismatch** — нестабильный доменный профиль + pending, нужна проверка.

### 3. Рекомендации

- **recommended_action** — что сделать.
- **urgency**: `high`, `medium`, `low`.
- **evidence_summary** — краткое обоснование.

## Когда handoff действительно нужен

- Pending approval — handoff executor → owner.
- Rework — handoff owner → executor.
- Runtime degraded — handoff operator → owner.
- Long-running / blockers — escalation operator → owner.

Handoff — это **рекомендация**, не автоматическое переназначение. Система не меняет lifecycle и не назначает задачи. Owner/GM принимает решение.

## Как owner/GM использовать hotspots

1. **approval_bottleneck** — выделить время на разбор approvals, /approvals или Dashboard.
2. **review_execution_loop** — уточнить постановку, провести краткий sync owner–executor.
3. **runtime_escalation_gap** — проверить Molt, логи, boundary; при необходимости эскалировать.
4. **owner_attention_gap** — открыть проект, посмотреть pending/rework, приоритизировать.
5. **domain_handoff_mismatch** — проверить доменный профиль проекта, /owner/domain.

## Как не путать role visibility и collaboration need

- **Role visibility** — что видит роль (tasks, approvals, artifacts). Это уже есть в role views.
- **Collaboration need** — **кто с кем** должен взаимодействовать, где flow застревает, какие handoff pending.

Collaboration добавляет слой «между кем и кем», а не «что видит одна роль».

## Когда recommendation говорит «подключить роль», а когда это наблюдение

- **Подключить роль** — явный handoff: executor_to_owner (owner должен принять решение), operator_to_owner (owner должен проверить runtime).
- **Наблюдение** — owner_attention_gap, domain_handoff_mismatch: система указывает на зону внимания, но не требует немедленного handoff. Owner решает, когда действовать.

## Где смотреть

- Dashboard: блок Collaboration (hotspots).
- /owner/collaboration — полная страница handoffs, hotspots, recommendations.
- /owner/portfolio — блок Collaboration hotspots.
- /owner/project/{key} — блок Collaboration (handoff signals по проекту).
- Role views (operator, executor, reviewer) — блок Collaboration.
- Telegram: /collaboration, /handoffs, /project_handoffs &lt;key&gt;, /role_collaboration &lt;role&gt;.
