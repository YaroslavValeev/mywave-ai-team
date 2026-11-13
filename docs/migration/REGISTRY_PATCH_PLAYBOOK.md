# Registry patch playbook (Phase 10.7)

## Как proposal превращается в patch candidate

1. Refinement proposal создаётся из backlog (Phase 10.6) и имеет тип, например `add_specialization_profile`, `adjust_routing_keywords`, `add_alias`.
2. После review owner выставляет статус `accepted`.
3. **Patch candidate** строится вызовом `build_patch_candidate(proposal_id)`: по типу и target_layer определяется `patch_type`, `target_file`, формируется `diff_summary` и флаг `apply_allowed` (только для safe types).

## Как читать dry-run

- Вызвать `dry_run_patch(proposal_id)` или POST `/api/owner/refinement/proposal/{id}/patch/dry-run`.
- В ответе: `diff_summary`, `validation_preview` (status ok/error, errors), `apply_allowed`.
- Файлы реестра при dry-run не меняются; показывается, что *будет* изменено и прошла ли валидация «нового» содержимого.

## Когда patch можно применять

- Proposal в статусе `accepted`.
- Patch type в whitelist safe (add_specialization_profile, append_* и т.д. по SAFE_PATCH_POLICY).
- Валидация `validate_patch_candidate(proposal_id)` возвращает `validation_status: ok`.
- Реализованный file-backed apply сейчас только для `add_specialization_profile` к `specializations.yaml`; остальные типы — export и ручное применение.

## Как читать validation

- Вызвать `validate_patch_candidate(proposal_id)` или POST `.../patch/validate`.
- `validation_status`: ok | error | skipped (не auto-applicable).
- При error — `validation_errors`: список строк (парсинг YAML, структура, дубликат ключа).

## Когда нужен manual apply

- Patch type не в safe whitelist (удаление, переименование, массовые изменения).
- `apply_allowed: false` в candidate.
- Валидация не прошла — исправить данные и повторить или применить изменение вручную по экспорту.

## Как работает rollback

- После успешного apply сохраняется `backup_ref` (путь к копии файла до изменения).
- `rollback_patch(patch_id)` восстанавливает целевой файл из backup_ref.
- Доступно только для зарегистрированных патчей (метаданные в `app/data/registry_patches.json`).

## Какие типы правок intentionally blocked

- Удаление ключей из specializations/domains.
- Переименование canonical keys.
- Массовое изменение структуры, слияние/разделение профилей.
- Для них возвращается `apply_allowed: false`, применять только вручную по экспорту.
