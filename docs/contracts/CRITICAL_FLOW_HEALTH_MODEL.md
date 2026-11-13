# CRITICAL_FLOW_HEALTH_MODEL — Критичные потоки и их здоровье

## Critical flows

| Flow | Что проверяем | Источник |
|------|---------------|----------|
| owner_dashboard | get_dashboard_overview не падает | owner_dashboard |
| owner_api | API отвечает (например /api/owner/domains или tasks) | api_router |
| telegram_baseline | TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID заданы | config |
| action_center | list_available_actions, can_execute_action работают | action_center |
| collaboration_execution | list_collaboration_executions / get_collaboration_execution не падают | collaboration_execution |
| tuning_refinement_patch | list_refinement_proposals, list_patchable_candidates не падают | refinement_proposals, tuning_patch_integration |
| domain_project_portfolio | list_projects, list_domains работают | project_queries, domain_registry |

## Проверка

- Вызвать соответствующую функцию/endpoint.
- При exception → flow failed.
- При успешном ответе (даже пустом) → flow ok.
