# Domain override — relation contract (Phase 10.1)

Краткая связь понятий: auto-selection, override, effective context, audit, owner visibility, workflow usage.

- **Auto-selection:** при triage по тексту задачи выбираются primary/secondary domains и context packs; результат — metadata и compact_context без override.
- **Override:** владелец может задать для задачи явный primary_domain через `/set_task_domain`; запись хранится в domain_override_store и активна до снятия.
- **Effective context:** при чтении контекста для задачи сначала проверяется override; если есть — используется он, иначе — результат auto-selection. Итог возвращается как workflow_domain_context (selected_primary_domain, compact_context, domain_override, reason, source).
- **Audit:** события domain_triage (авто-подбор), domain_override (установка/снятие override), domain_context_used (использование контекста в workflow) пишутся в audit trail.
- **Owner visibility:** в карточке задачи (/task, dashboard) показываются effective domain и признак override с краткой причиной; отдельная команда /task_domain выводит только effective domain и override status.
- **Workflow usage:** effective domain context передаётся в pipeline (handoff) и court (report); рекомендации (domain-aware signals) группируют задачи по effective domain.

Граница: domain override не влияет на permissions, policy или approve-правила.
