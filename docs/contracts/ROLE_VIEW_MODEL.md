# Role view model (Phase 9.7)

Формализация view по ролям: source of truth, блоки, команды, freshness, fallback.

---

## owner_view

- **Source of truth:** owner_dashboard (get_dashboard_overview, get_dashboard_next_actions, get_dashboard_blockers, get_dashboard_decision_queue, get_dashboard_project_health, get_dashboard_recent_artifacts, get_dashboard_digest_preview); при необходимости owner_portfolio (get_portfolio_overview, get_portfolio_focus_list).
- **Primary widgets/blocks:** Overview, next actions, blockers, decision queue, project health, recent artifacts, digest preview (как на /owner).
- **Primary commands:** Существующие owner-команды; /view_owner — компактный текстовый summary для Telegram.
- **Freshness:** При каждой загрузке страницы / вызове команды.
- **Fallback:** При ошибке — сообщение «Data unavailable», пустые списки где применимо.

---

## operator_view

- **Source of truth:** owner_queries.get_system_status_summary(); owner_insights.get_blockers_summary(), get_long_running_summary(); при degraded — явный state и molt_message.
- **Primary widgets/blocks:** Runtime status (transport, Molt health, state), degraded cue, blockers count/items, long-running/stuck count/items, active_tasks_count.
- **Primary commands:** /view_operator (Telegram), GET /views/operator (web).
- **Freshness:** При запросе.
- **Fallback:** state = Unknown, molt_ok = False при ошибке; пустые списки для blockers/long_running.

---

## executor_view

- **Source of truth:** owner_queries.get_active_tasks(), get_recent_artifacts(); owner_insights.get_blockers_summary() (blocked/stuck как контекст).
- **Primary widgets/blocks:** Active tasks (id, status, кратко), recent artifacts (task id, summary/report_path), blockers (что блокирует).
- **Primary commands:** /view_executor (Telegram), GET /views/executor (web).
- **Freshness:** При запросе.
- **Fallback:** Пустые списки при ошибке.

---

## reviewer_view

- **Source of truth:** owner_queries.get_pending_approvals(); owner_recommendations.get_decision_queue() или owner_insights.get_awaiting_decisions_summary().
- **Primary widgets/blocks:** Pending approvals list, decision queue (reason, priority, suggested action).
- **Primary commands:** /view_reviewer (Telegram), GET /views/reviewer (web).
- **Freshness:** При запросе.
- **Fallback:** Пустые списки, pending_count = 0.
