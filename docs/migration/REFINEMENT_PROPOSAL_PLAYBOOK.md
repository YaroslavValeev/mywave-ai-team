# Refinement proposal playbook (Phase 10.6)

## Как proposal появляется

- **Источник:** refinement backlog (Phase 10.5), который строится из refinement signals (override-heavy domain/project, frequent fallback domain+step, unstable execution lane).
- **Генерация:** вызов `generate_refinement_proposals(window_days=30)` или в Telegram `/refinement_proposals generate`, или POST `/api/owner/refinement/proposals/generate`. Система берёт элементы backlog и создаёт по ним записи proposal со статусом `proposed`; дубликаты по тому же refinement_item_key не создаются, если уже есть запись не в статусе rejected/proposed.
- **Поля:** proposal_id, proposal_type, target_layer, target_key, reason, evidence_summary, recommended_change, source_signals, severity, status=proposed.

## Как делать review

- **Web:** открыть `/owner/refinement/proposals?status=proposed`, перейти в карточку proposal, для принятия/отклонения использовать API: POST `/api/owner/refinement/proposal/{id}/review` с body `{"decision": "accept"|"reject", "notes": "..."}`.
- **Telegram:** `/refinement_proposal <id>` — карточка; `/review_refinement <id> accept` или `/review_refinement <id> reject заметка`.
- **Решение:** accept переводит в `accepted`, reject — в `rejected`. Оба варианта сохраняются; reviewed_at и reviewer записываются; в audit пишутся события refinement_proposal_reviewed, refinement_proposal_accepted/rejected.

## Когда accept, когда reject

- **Accept:** если owner согласен с рекомендуемым изменением и готов его применить (вручную или через экспорт патча).
- **Reject:** если предложение неактуально, дублирует другое, или по другой причине не должно быть применено. Rejected остаётся в истории для прозрачности.

## Что значит apply

- **Apply** — отметка «изменение применено»: либо фактически внесено в реестр (вручную по экспорту), либо выполнено автоматизированно (если реализовано для данного типа). Вызов: POST `/api/owner/refinement/proposal/{id}/apply` или аналог. Статус переходит в `applied`, фиксируются applied_at и reviewer; в audit пишется refinement_proposal_applied.
- **accepted ≠ applied:** принятие означает согласие с изменением; применение — факт внесения изменения.

## Как читать candidate patch

- **Экспорт:** GET `/api/owner/refinement/proposal/{id}/export` возвращает patch_candidate: target_file, action, human_instruction, при необходимости yaml_suggestion.
- **human_instruction** — краткая инструкция, что сделать вручную.
- **yaml_suggestion** — для add_specialization_profile выдаётся пример блока YAML для вставки в specializations.yaml.
- По этому кандидату owner вносит правку в репозиторий, после чего может отметить proposal как applied.

## Что делать вручную, если auto-apply не предусмотрен

- Для типов add_specialization_profile, adjust_routing_keywords, add_alias: открыть соответствующий файл реестра, внести изменение по human_instruction и (если есть) yaml_suggestion, сохранить, затем отметить proposal как applied через API или вручную в хранилище предложений (не рекомендуется менять JSON вручную — лучше через API apply).
