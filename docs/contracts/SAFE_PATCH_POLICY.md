# Safe patch policy (Phase 10.7)

## Что можно применять автоматически / semi-automatically

- **add_alias** — добавить алиас в список aliases домена (domain_registry или domain_aliases). Risk: low. Requires: accepted proposal, dry-run, backup.
- **append_routing_keyword** — добавить ключевое слово в routing_keywords домена. Risk: low. Requires: accepted proposal, dry-run, backup.
- **append_typical_request** — добавить в typical_requests. Risk: low. Requires: accepted proposal, dry-run, backup.
- **append_specialization_keyword** — добавить в selection_keywords существующего профиля специализации. Risk: low. Requires: accepted proposal, dry-run, backup.
- **append_guardrail_note** — добавить элемент в guardrails. Risk: low. Requires: accepted proposal, dry-run, backup.
- **add_specialization_profile** — добавить новую запись в specializations (новый ключ). Risk: low при отсутствии перезаписи. Requires: accepted proposal, dry-run, backup.
- **update_summary_minor** — обновить поле summary у существующей записи (короткое текстовое поле). Risk: low. Requires: accepted proposal, dry-run, backup.

Rollback supported: да, для всех перечисленных (восстановление из backup файла).

## Что нельзя применять автоматически

- Удаление ключей из registry.
- Переименование canonical keys (domain_key, specialization_key).
- Массовое изменение структуры (слияние доменов, смена иерархии).
- Изменение fundamental domain mapping (canonical → domain).
- Сложное объединение/разделение профилей.

Для таких изменений: export candidate + manual apply; в API возвращается apply_allowed: false, reason: "high-risk or unsupported patch type".

## Правила

- **requires accepted proposal** — apply_patch_candidate вызывается только для proposal со status=accepted.
- **requires dry-run** — перед apply рекомендуется или обязательно выполнить dry_run_patch и показать результат owner.
- **requires backup** — перед записью в файл создаётся snapshot; backup_ref сохраняется в audit и в метаданных патча.
- **validation** — validate_patch_candidate должна вернуть ok перед apply; при ошибке парсинга или дубликата apply не выполняется.
