# Domain prompt and override — relation (Phase 10.2)

Краткая связь понятий.

- **Domain auto-selection** — по тексту задачи выбираются primary/secondary и context packs; результат в effective_domain_context.
- **Effective context** — при наличии активного override используется он, иначе auto-selection; один объект на задачу (selected_primary_domain, compact_context, domain_override, reason, source).
- **Step-specific prompts** — из effective context для каждого шага (pipeline, roundtable, court) строится свой профиль: свой срез секций, лимит длины, step_specific_focus; контекст точнее, а не длиннее.
- **Override set** — `/set_task_domain` или web apply; запись в store; audit domain_override.
- **Override clear** — `/clear_task_domain` или web clear; override_active=false; audit domain_override_cleared; effective context снова = auto.
- **Audit** — domain_triage, domain_override, domain_override_cleared, domain_context_used.
- **Owner visibility** — task card / task detail: effective domain, override yes/no, причина; опционально step-specific hint (pipeline-focused, court risk emphasis); debug endpoint — полный domain-context для задачи.
- **Workflow usage** — pipeline/roundtable/court получают step-specific domain prompt от domain_prompt_profiles; fallback к общему compact_context при отсутствии профиля.
