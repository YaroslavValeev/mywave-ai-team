# Phase 10.5 — Acceptance (Override analytics and adaptive specialization refinement)

## Что считается завершённым

- [x] ADR-039 зафиксирован (override analytics, refinement, принципы, non-goals).
- [x] Override analytics model описана (DOMAIN_OVERRIDE_ANALYTICS_MODEL).
- [x] Specialization analytics model описана (SPECIALIZATION_ANALYTICS_MODEL).
- [x] Refinement signal heuristics описаны (REFINEMENT_SIGNAL_HEURISTICS).
- [x] Refinement backlog model описана (REFINEMENT_BACKLOG_MODEL).
- [x] Relation doc (DOMAIN_OVERRIDE_FALLBACK_REFINEMENT_RELATION).
- [x] Analytics service: `app/services/domain_specialization_analytics.py` (get_domain_override_summary, get_override_hotspots, get_specialization_fallback_summary, get_specialization_hotspots, get_refinement_signals, get_refinement_backlog).
- [x] Presenters: `app/presenters/domain_specialization_analytics_presenters.py` (present_* и format_*_telegram).
- [x] Web: `/owner/refinement`, шаблон owner_refinement.html, навигация Refinement в owner dashboard.
- [x] API: `GET /api/owner/refinement?window_days=30`.
- [x] Telegram: `/domain_analytics [дней]`, `/specialization_analytics [дней]`, `/refinement_backlog [дней]`.
- [x] Owner recommendations: в get_domain_aware_signals добавлены refinement_signals из get_refinement_signals.
- [x] Playbooks: DOMAIN_ANALYTICS_PLAYBOOK, REFINEMENT_BACKLOG_PLAYBOOK.
- [x] Тесты: shape, hotspots, presenters, routes/commands, recommendations, регрессия 10.0–10.4.

## Что остаётся следующим этапом

- Deeper project-domain lifecycle.
- Stronger collaboration flows.
- Optional explanation assist.
- Semi-manual registry refinement workflow.
- Agent-specific tuning workflow.
