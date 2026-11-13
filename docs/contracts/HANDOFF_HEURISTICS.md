# Handoff heuristics (Phase 10.9)

Explainable правила для handoff и collaboration signals.

## approval_bottleneck

- **Condition:** много задач в WAIT_OWNER/APPROVED_WAIT_MERGE (≥ 2).
- **Source:** get_awaiting_decisions_summary, get_pending_approvals.
- **Handoff:** executor_to_owner; target=owner.
- **Next role:** owner.
- **Why:** Исполнение завершено, решения owner блокируют поток.

## review_execution_loop

- **Condition:** rework_cycles ≥ 2 или много REWORK в одном проекте/домене.
- **Source:** get_rework_signal_summary, project-level aggregation.
- **Handoff:** owner↔executor loop.
- **Next role:** owner + executor coordination.
- **Why:** Повторные rework указывают на разрыв между ожиданиями owner и результатом executor.

## runtime_escalation_gap

- **Condition:** system state DEGRADED или много блокеров/long-running.
- **Source:** get_degraded_signal_summary, get_blockers_summary, get_long_running_summary.
- **Handoff:** operator_to_owner.
- **Next role:** operator (снять блокеры) → owner (если нужна эскалация).
- **Why:** Runtime нестабилен; operator должен вовлечь owner.

## owner_attention_gap

- **Condition:** в проекте одновременно pending approvals + long-running или rework.
- **Source:** project_queries (pending, long_running, rework по project).
- **Handoff:** несколько потоков сходятся к owner.
- **Next role:** owner.
- **Why:** Owner перегружен несколькими типами решений в одном проекте.

## domain_handoff_mismatch

- **Condition:** override-heavy проект + pending approvals; или project_domain lifecycle unstable.
- **Source:** project_domain_mapping mismatch_signals, project_domain_lifecycle.
- **Handoff:** контекст handoff неясен из-за доменной нестабильности.
- **Next role:** owner/GM (уточнить домен или refinement).
- **Why:** Частые override могут означать, что triage/domain контекст неверен при handoff.
