# Refinement proposal persistence (Phase 10.6)

## Где хранятся proposals

- **Вариант (реализован):** один JSON-файл, например `app/data/refinement_proposals.json`, ключ — `proposals`, значение — объект с ключами `proposal_id` и значениями — записями proposal (все поля модели).
- Альтернатива: отдельная таблица в БД (RefinementProposal); при необходимости миграции можно ввести позже.

## Где хранятся review/apply статусы

- В той же записи proposal: поля `status`, `reviewed_at`, `applied_at`, `reviewer`, `notes`. Отдельного хранилища для «истории ревью» на этом этапе не требуется; при необходимости можно добавить массив `review_history`.

## Связь с audit

- При создании proposal — вызов log_audit(repo, "refinement_proposal_created", payload={proposal_id, proposal_type, target_layer}).
- При review — refinement_proposal_reviewed / refinement_proposal_accepted / refinement_proposal_rejected.
- При apply — refinement_proposal_applied.
- При экспорте — refinement_change_exported.
- audit_events хранятся в существующей таблице audit_events (task_id опционально, payload содержит proposal_id и контекст).

## Кодовый слой

- **refinement_proposal_store.py** — функции: _load(), _save(), list_proposals(status=None), get_proposal(proposal_id), save_proposal(proposal), update_proposal_status(proposal_id, status, **kwargs). Файл данных задаётся через путь в модуле или env (REFINEMENT_PROPOSALS_PATH).
