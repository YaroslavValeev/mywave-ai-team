# Phase 10.3 — Acceptance

## Что считается завершённым

- [x] Project–domain mapping model описана (PROJECT_DOMAIN_MAPPING_MODEL, heuristics).
- [x] Role–domain recommendation model описана (ROLE_DOMAIN_RECOMMENDATION_MODEL, ROLE_DOMAIN_HEURISTICS).
- [x] Heuristics описаны (PROJECT_DOMAIN_HEURISTICS, ROLE_DOMAIN_HEURISTICS).
- [x] Service layers: project_domain_mapping.py, role_domain_recommendations.py.
- [x] Presenters: project_domain_presenters.py, role_domain_presenters.py; project/role views показывают domain (dominant в списке и карточке проекта; domain_recommendations в role views).
- [x] Project views: /projects, /project &lt;key&gt;, Dashboard — dominant domain, domain profile в карточке, mismatch при наличии.
- [x] Role views: owner/operator/executor/reviewer — domain_recommendations в данных и в Telegram (Domain focus / Domain pressure).
- [x] Telegram: /project_domain &lt;key&gt;, /role_domains, /domain_pressure.
- [x] Recommendations: project_domain_signals (override-heavy, mismatch по проектам) в get_domain_aware_signals.
- [x] Playbooks и relation docs (PROJECT_DOMAIN_PLAYBOOK, ROLE_DOMAIN_PLAYBOOK, PROJECT_DOMAIN_ROLE_TRIANGLE).
- [x] ADR-037 и acceptance doc.
- [x] Тесты: shape, dominant explainable, mismatch, role recommendations, project/role visibility, cross-project summary, commands wired, регрессия 9.9–10.2.

## Что остаётся следующим этапом

- Deeper agent specialization.
- Stronger override analytics.
- Richer project–domain lifecycle.
- Optional LLM explanation assist.
- Domain-aware collaboration flows.
