# Refinement lifecycle model (Phase 10.6)

## Этапы

1. **Analytics produces signals** — domain_specialization_analytics генерирует refinement signals и backlog (Phase 10.5).
2. **Signals become proposals** — сервис refinement_proposals вызывает generate_refinement_proposals; для выбранных элементов backlog создаются записи proposal со status=proposed.
3. **Proposal goes to review queue** — список proposals со status proposed (или reviewed без решения) доступен owner/GM через web и Telegram.
4. **Owner/GM reviews** — просмотр proposal (reason, evidence, target_layer, target_key); решение принять или отклонить.
5. **Proposal accepted/rejected** — review_refinement_proposal(proposal_id, decision="accept"|"reject", reviewer, notes); status переходит в accepted или rejected; reviewed_at и reviewer сохраняются.
6. **Accepted proposal can be applied** — для accepted вызывается mark_refinement_proposal_applied или выполняется экспорт candidate и ручное применение; status=applied, applied_at фиксируется.
7. **Application gets audited** — событие refinement_proposal_applied (и при необходимости refinement_change_exported) пишется в audit.
8. **System can later verify** — при следующем прогоне аналитики можно проверить, уменьшились ли соответствующие hotspots/signals (out of scope текущего этапа, но lifecycle это допускает).

## Важно

- **accepted ≠ applied** — принятие означает «согласовано к применению»; применение — отдельный шаг (автоматический apply или ручной по экспорту).
- **rejected сохраняется в истории** — статус rejected не удаляет proposal; нужен для прозрачности и повторного анализа.
- **Apply always auditable** — любое применение (или экспорт для ручного применения) фиксируется в audit.
