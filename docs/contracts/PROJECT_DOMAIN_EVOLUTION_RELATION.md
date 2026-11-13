# Project-domain evolution relation (Phase 10.8)

Связь между сущностями по пути от задачи до lifecycle и рекомендаций.

- **Task domain** — домен задачи (triage/domain на задаче).
- **Effective domain** — выбранный домен с учётом override (workflow_domain_context): selected_primary_domain, domain_override.
- **Project-domain profile** — агрегат по задачам проекта: dominant_domain, distribution, override_count, mismatch_signals (Phase 10.3).
- **Lifecycle signal** — эволюция за окно: previous vs current подокно, drift, diversification, instability, lifecycle_state (Phase 10.8).
- **Portfolio signal** — проекты с drift / override-heavy / unstable показываются в портфеле и в hotspot-блоках.
- **Refinement / recommendation impact** — рекомендации могут включать project_domain_drift_signal, project_domain_instability_signal, project_domain_diversification_attention, override_heavy_project_domain_signal; refinement backlog может учитывать нестабильные проекты.

Итог: task → effective domain → project profile (snapshot) → lifecycle (previous/current, state) → portfolio/recommendations.
