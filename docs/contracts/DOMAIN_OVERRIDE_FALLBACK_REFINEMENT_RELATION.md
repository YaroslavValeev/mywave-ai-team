# Domain override – fallback – refinement relation (Phase 10.5)

Краткая связь понятий.

- **Override** — владелец явно задал primary domain для задачи (surface: set_task_domain / domain-override API). В audit пишется `domain_override`; при снятии — `domain_override_cleared`. Аналитика агрегирует эти события → override summary, override by domain/project, override hotspots.

- **Fallback** — для пары (domain, workflow_step) в реестре специализаций нет профиля, система подставила general_pipeline / general_roundtable / general_court. В audit пишется `specialization_fallback_used` (или при выборе профиля — `specialization_selected`). Аналитика агрегирует → fallback summary, fallback by domain/step, fallback hotspots.

- **Mismatch** — эффективный домен не general, но выбранная специализация — general_* (домен определён, а execution profile универсальный). Частный случай слабого execution lane. Учитывается в specialization analytics и в refinement signals.

- **Hotspot** — зона концентрации: домен или проект с высоким числом override; или пара (domain, step) с высоким числом fallback. Пороги задаются эвристиками (например >= 2 за окно). Hotspots входят в override_hotspots и specialization_hotspots.

- **Refinement backlog** — список рекомендаций для owner/GM: что улучшить вручную (добавить/расширить профиль, поправить keywords, проверить override reasons). Строится из refinement signals; не хранится отдельно, генерируется на лету из аналитики.

- **Recommendation signal** — в owner recommendations (get_domain_aware_signals, get_risk_signals и т.д.) могут включаться сигналы типа override_heavy_domain, specialization_fallback_hotspot, project_needing_refinement. Только explainable, без автодействий; не смешивать с операционными алертами (blockers, approvals).

Итог: override и fallback — сырые факты в audit; аналитика агрегирует их в summary и hotspots; эвристики превращают в refinement signals и backlog; recommendation layer может показывать часть из них owner-у для внимания.
