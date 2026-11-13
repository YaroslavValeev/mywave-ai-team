# Refinement audit model (Phase 10.6)

## События

- **refinement_proposal_created** — создано предложение из analytics. Payload: proposal_id, proposal_type, target_layer, target_key, severity.
- **refinement_proposal_reviewed** — по предложению проведено ревью. Payload: proposal_id, decision (accept/reject), reviewer, notes (optional).
- **refinement_proposal_accepted** — предложение принято (может совпадать с reviewed при decision=accept или отдельное событие для ясности). Payload: proposal_id, reviewer.
- **refinement_proposal_rejected** — предложение отклонено. Payload: proposal_id, reviewer, notes (optional).
- **refinement_proposal_applied** — предложение отмечено как применённое (фактическое изменение реестра или ручное применение по экспорту). Payload: proposal_id, reviewer, notes (optional).
- **refinement_change_exported** — экспортирован candidate patch для предложения. Payload: proposal_id, export_format (e.g. yaml_patch, json_delta).

## Где писать

- Существующий механизм log_audit(repo, event_type, task_id=None, payload=...) — task_id для refinement может быть None; payload содержит proposal_id и контекст.
- Репозиторий (repo) передаётся из вызывающего кода (web handler, Telegram handler, service при наличии доступа к сессии).

## Связь с proposal

- По proposal_id можно восстановить цепочку: created → reviewed → accepted/rejected → (optional) applied, (optional) change_exported.
