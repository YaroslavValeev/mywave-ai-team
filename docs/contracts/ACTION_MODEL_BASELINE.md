# Action model baseline (Phase 9.8)

Минимальный набор безопасных действий с категориями, ролями и ожидаемым эффектом.

---

## Категории действий

- **informational_action** — обновление/получение данных без изменения состояния системы (refresh, open queue).
- **control_action** — запрос отчёта/сводки по запросу пользователя (send summary now, send digest now).
- **recovery_action** — проверка состояния runtime и восстановление видимости (recheck health, smoke-check, acknowledge degraded).
- **workflow_action** — обновление кэша/списков для workflow (rebuild focus list, refresh project summary).

---

## Baseline-действия

| action_name | category | purpose | allowed_roles | approval_required | safe/idempotent |
|-------------|----------|---------|---------------|-------------------|------------------|
| refresh_status | informational | Обновить сводку состояния (status) | owner, operator, executor, reviewer | no | yes |
| refresh_project_view | informational | Обновить данные по проекту для view | owner, executor | no | yes |
| send_summary_now | control | Отправить текущую развёрнутую сводку в Telegram | owner | no | yes |
| send_digest_now | control | Отправить стратегический digest сейчас | owner | no | yes |
| recheck_molt_health | recovery | Проверить Molt health заново | owner, operator | no | yes |
| run_smoke_check | recovery | Выполнить smoke-check runtime | owner, operator | no | yes |
| acknowledge_degraded | recovery | Зафиксировать, что degraded отмечен (audit) | owner, operator | no | yes |
| retry_runtime_check | recovery | Повторная проверка runtime после сбоя | owner, operator | no | yes |
| rebuild_focus_list | workflow | Пересобрать focus list для portfolio | owner | no | yes |
| notify_owner_now | control | Отправить уведомление owner (summary) | owner | no | yes |
| open_decision_queue | informational | «Открыть» очередь решений (refresh + возврат данных) | owner, reviewer | no | yes |
| trigger_project_summary | control | Сформировать и отправить summary по проекту | owner | no | yes |

**Source of truth:** существующие слои (owner_queries, owner_insights, owner_notifications, owner_recommendations, project_queries, runtime health). Action center только оркестрирует вызовы.

**Expected effect:** каждый action возвращает result_summary (успех/ошибка, краткое описание). Никаких необратимых изменений задач/approvals — только read + optional send notification.
