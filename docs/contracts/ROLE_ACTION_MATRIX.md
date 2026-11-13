# Role–action matrix (Phase 9.8)

Минимальная практическая матрица: какие роли могут выполнять какие действия.

---

## Owner

- **Все safe informational и control actions:** refresh_status, refresh_project_view, send_summary_now, send_digest_now, notify_owner_now, open_decision_queue, trigger_project_summary.
- **Recovery actions:** recheck_molt_health, run_smoke_check, acknowledge_degraded, retry_runtime_check.
- **Workflow:** rebuild_focus_list.
- **Ограничения:** без destructive; approve/rework остаются через существующий flow.

---

## Operator

- **Recovery:** recheck_molt_health, run_smoke_check, acknowledge_degraded, retry_runtime_check.
- **Informational:** refresh_status.
- **Не может:** send_summary_now, send_digest_now, notify_owner_now, open_decision_queue, trigger_project_summary, rebuild_focus_list, refresh_project_view (только owner/executor).

---

## Executor

- **Informational:** refresh_status.
- **Workflow-like (refresh work view):** по сути refresh_status даёт active tasks/artifacts/blockers.
- **Не может:** runtime recovery (recheck, smoke, acknowledge), digest/summary send, decision queue control, rebuild_focus_list.

---

## Reviewer

- **Informational:** refresh_status, open_decision_queue.
- **Не может:** send_summary_now, send_digest_now, recheck_molt_health, run_smoke_check, acknowledge_degraded, retry_runtime_check, rebuild_focus_list, trigger_project_summary, refresh_project_view.

---

## Итог

- **Не full RBAC** — минимальный практический scope.
- При попытке выполнить неразрешённое действие возвращается явная ошибка (role not allowed).
- Матрица задаётся в action_center (registry) и проверяется в can_execute_action / execute_action.
