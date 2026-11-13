# Owner insight model (Phase 9.2)

## `weekly_digest`
- purpose: недельная управленческая картина.
- source of truth: tasks, decisions, audit_events, status summary.
- aggregation: окно 7 дней.
- output shape: completed_count, approvals_count, rework_count, blockers_count, degraded_events_count, owner_focus.
- freshness: 1 раз в неделю.

## `blockers_summary`
- purpose: что прямо тормозит.
- source: awaiting decisions + long running + degraded state.
- aggregation: текущий снимок + эвристики.
- output: blockers_count, degraded_now, items[].
- freshness: on-demand/команда.

## `awaiting_decisions_summary`
- purpose: что ждёт решения owner.
- source: Task.status in WAIT_OWNER/APPROVED_WAIT_MERGE.
- aggregation: snapshot.
- output: pending_count, items[].
- freshness: on-demand.

## `completed_recently_summary`
- purpose: что завершено недавно.
- source: tasks DONE + artifacts.
- aggregation: updated_at за 7 дней.
- output: completed_count, artifact_count, items[].
- freshness: on-demand.

## `project_activity_summary`
- purpose: baseline project-level движение.
- source: task.domain/task_type fallback.
- aggregation: группировка и top-N.
- output: projects_count, top_projects[].
- freshness: on-demand/weekly.

## `rework_signal_summary`
- purpose: выявить repeated rework.
- source: task.rework_cycles, task.status.
- aggregation: cycles>=2 или статус REWORK.
- output: count, items[].
- freshness: on-demand/weekly.

## `degraded_signal_summary`
- purpose: показать операционную нестабильность.
- source: system status + audit_events.
- aggregation: события error/degraded/rollback за 7 дней.
- output: current_state, molt_ok, events_count_7d, events[].
- freshness: on-demand/weekly.

## `long_running_summary`
- purpose: показать stale/затянувшиеся задачи.
- source: task.status + updated_at.
- aggregation: thresholds по времени (см. OWNER_INSIGHT_HEURISTICS).
- output: count, items[].
- freshness: on-demand.
