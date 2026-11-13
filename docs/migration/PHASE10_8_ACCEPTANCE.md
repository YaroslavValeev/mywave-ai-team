# Phase 10.8 — Project-domain lifecycle and domain evolution signals (Acceptance)

## Что считается завершённым

- **Lifecycle model** — описана в docs/contracts/PROJECT_DOMAIN_LIFECYCLE_MODEL.md (current/previous dominant, stability, drift/diversification/instability, lifecycle_state, window_days).
- **Heuristics** — docs/contracts/PROJECT_DOMAIN_LIFECYCLE_HEURISTICS.md: explainable правила для stable_single_domain, stable_multi_domain, drifting, override_heavy, unstable, weak_signal.
- **Service layer** — app/services/project_domain_lifecycle.py: get_project_domain_lifecycle, list_project_domain_lifecycles, get_project_domain_drift_signals, get_project_domain_diversification_signals, get_project_domain_instability_signals, get_cross_project_domain_lifecycle_summary.
- **Presenters** — app/presenters/project_domain_lifecycle_presenters.py: present_project_domain_lifecycle, present_domain_drift_signals, present_domain_diversification_signals, present_domain_instability_signals, present_cross_project_domain_lifecycle_summary, format_project_lifecycle_telegram, format_domain_lifecycle_telegram.
- **Project view** — /owner/project/{key}: блок «Domain lifecycle» (state, reason, drift/instability).
- **Portfolio view** — /owner/portfolio: блок «Domain lifecycle» (дрифтующие, нестабильные/override-heavy).
- **API** — GET /api/owner/project/{key}/lifecycle, GET /api/owner/domain-lifecycle.
- **Telegram** — /project_lifecycle &lt;key&gt;, /domain_lifecycle [days].
- **Recommendations** — project_domain_drift_signal, project_domain_instability_signal в get_next_actions; project_domain_lifecycle_signals в get_domain_aware_signals.
- **Playbooks** — PROJECT_DOMAIN_LIFECYCLE_PLAYBOOK.md, DOMAIN_DRIFT_PLAYBOOK.md.
- **Relation** — docs/contracts/PROJECT_DOMAIN_EVOLUTION_RELATION.md.
- **ADR** — ADR-042-project-domain-lifecycle-and-evolution-signals.md.
- **Тесты** — сценарии A–I (shape, stable_single_domain, drifting, override_heavy/unstable, views, portfolio, recommendations, commands, регрессия).

## Что остаётся следующим этапом

- Collaboration flows.
- Explanation assist.
- Richer semi-automated tuning.
- Agent-specific tuning workflows.
- Domain-aware collaboration patterns.
