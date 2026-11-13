# Analytics to refinement relation (Phase 10.6)

Связь между Phase 10.5 и 10.6.

- **Signal** — результат эвристик аналитики (override_heavy_domain, frequent_fallback_domain_step и т.д.); выдаётся get_refinement_signals.
- **Hotspot** — агрегированная зона (domain или project для override; domain+step для specialization); выдаётся get_override_hotspots, get_specialization_hotspots.
- **Refinement backlog** — список actionable items, построенный из signals (get_refinement_backlog); каждый элемент содержит reason, recommended_change, evidence_summary.
- **Proposal** — запись в refinement proposal store, сгенерированная из элемента backlog (или из signal); имеет proposal_id, status, target_layer, target_key; связь с источником — source_signals / refinement_item_key.
- **Review** — действие owner/GM по proposal: просмотр, решение accept/reject, опционально notes; статус proposal переходит в accepted или rejected.
- **Apply** — отметка, что изменение применено (фактически в реестре или вручную по экспорту); статус applied; запись в audit.
- **Audit** — все ключевые события (created, reviewed, accepted, rejected, applied, change_exported) пишутся в audit_events для прослеживаемости.

Итог: аналитика производит сигналы и backlog → сервис генерирует proposals → owner ревьюит и принимает/отклоняет → принятые можно применить (или экспортировать и применить вручную) → всё фиксируется в audit.
