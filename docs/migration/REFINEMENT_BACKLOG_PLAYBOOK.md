# Refinement backlog playbook (Phase 10.5)

## Что такое refinement backlog

Список рекомендаций по улучшению domain routing и specialization layer: где чаще всего правит owner (override), где часто срабатывает fallback, где стоит добавить или расширить профиль. Backlog **генерируется на лету** из аналитики (audit events), отдельной таблицы для backlog нет.

## Как owner/GM используют backlog

- **Web**: страница `/owner/refinement` — блоки Override summary, Override hotspots, Specialization fallback summary, Specialization hotspots, Refinement signals, Refinement backlog.
- **Telegram**: команда `/refinement_backlog [дней]` — краткий список пунктов с severity, причиной и рекомендуемым действием.
- **API**: `GET /api/owner/refinement?window_days=30` — JSON со всеми блоками для интеграций или своих дашбордов.

## Типы пунктов backlog

- **override_heavy_domain** — много override на один домен → проверить routing/keywords для этого домена.
- **override_heavy_project** — много override в одном проекте → просмотреть причины по задачам, возможно пресет домена.
- **frequent_fallback_domain_step** — частый fallback на паре (domain, step) → добавить/расширить профиль специализации.
- **unstable_execution_lane** — высокий общий fallback rate → расширить реестр или уточнить домены задач.

У каждого пункта: severity (low/medium), reason, recommended_change (add/expand profile, improve routing keywords, inspect override reasons manually и т.д.), evidence_summary.

## Что делать по рекомендации

- **add/expand specialization profile** — открыть реестр `app/data/agent_specializations/specializations.yaml`, добавить или доработать запись для указанного domain_key и workflow_step.
- **improve routing keywords** — проверить domain registry (keywords, алиасы) для указанного домена.
- **inspect override reasons manually** — по задачам из hotspot посмотреть, почему owner ставил override; при необходимости скорректировать формулировки или пресеты.
- **review alias map** — проверить маппинг алиасов доменов в конфигурации.

Система не применяет изменения сама — только подсказывает. Внедрение решений остаётся за owner/GM.
