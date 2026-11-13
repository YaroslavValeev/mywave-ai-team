# Owner dashboard model (Phase 9.4)

Модель блоков owner dashboard: source of truth, ожидание обновления, форма вывода, fallback при недоступности данных.

---

## dashboard_header_status

- **Source of truth:** owner_queries.get_system_status_summary().
- **Refresh:** при каждой загрузке страницы (read-only, no polling в baseline).
- **Output shape:** `{ state, transport_mode, molt_ok, molt_message, active_tasks_count, pending_approvals_count, recent_artifacts_count }` + при необходимости флаги для визуального cue (OK / DEGRADED / Attention needed).
- **Fallback:** при ошибке запроса — показать "Data unavailable", state = "Unknown".

---

## dashboard_next_actions

- **Source of truth:** owner_recommendations.get_next_actions(limit).
- **Refresh:** при загрузке страницы.
- **Output shape:** список `{ action_type, task_id, reason, priority, suggested_action, if_deferred }`.
- **Fallback:** пустой список, заголовок "Next actions" без ошибки.

---

## dashboard_blockers

- **Source of truth:** owner_insights.get_blockers_summary(limit).
- **Refresh:** при загрузке страницы.
- **Output shape:** `{ blockers_count, items: [ { task, kind } ] }` → для web: список с task_id, summary, kind.
- **Fallback:** blockers_count=0, items=[].

---

## dashboard_decision_queue

- **Source of truth:** owner_recommendations.get_decision_queue(limit).
- **Refresh:** при загрузке страницы.
- **Output shape:** список `{ task_id, reason, priority, suggested_next_action, if_ignored }`.
- **Fallback:** пустой список.

---

## dashboard_project_health

- **Source of truth:** owner_recommendations.get_project_health_summary(limit).
- **Refresh:** при загрузке страницы.
- **Output shape:** список `{ project, status, reason, active_count, pending_count, rework_signals, long_running }`.
- **Fallback:** пустой список.

---

## dashboard_recent_artifacts

- **Source of truth:** owner_queries.get_recent_artifacts(limit) или owner_insights.get_completed_recently_summary(limit).
- **Refresh:** при загрузке страницы.
- **Output shape:** список задач с id, summary, report_path, updated_at (или эквивалент).
- **Fallback:** пустой список.

---

## dashboard_operational_summary

- **Source of truth:** owner_summary.build_detailed_summary() или агрегат get_system_status_summary + top_tasks, pending_approvals_list, recent_artifacts_list.
- **Refresh:** при загрузке страницы.
- **Output shape:** структура для отображения operational snapshot (как /summary, но в виде view-model для web).
- **Fallback:** минимальный объект с сообщением "Unavailable".

---

## dashboard_weekly_digest_preview

- **Source of truth:** owner_recommendations.get_strategic_weekly_digest().
- **Refresh:** при загрузке страницы.
- **Output shape:** window_days, completed_count, key_risks, needs_decision, next_week_priorities, owner_focus и т.д. (view-model, без сырых ORM).
- **Fallback:** пустой preview с window_days=7.

---

## dashboard_monthly_digest_preview

- **Source of truth:** owner_recommendations.get_monthly_digest_baseline().
- **Refresh:** при загрузке страницы.
- **Output shape:** window_days, completed_count, active_count, pending_approvals_count, top_recommendations и т.д.
- **Fallback:** пустой preview с window_days=30.
