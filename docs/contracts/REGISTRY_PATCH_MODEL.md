# Registry patch model (Phase 10.7)

## Поля

- **patch_id** — уникальный идентификатор патча (например patch_<proposal_id>_<timestamp>).
- **proposal_id** — связь с refinement proposal.
- **target_layer** — specializations | domain_registry | domain_aliases.
- **target_file** — путь к файлу (app/data/agent_specializations/specializations.yaml и т.д.).
- **patch_type** — add_alias | append_routing_keyword | append_typical_request | append_specialization_keyword | append_guardrail_note | update_summary_minor | add_specialization_profile.
- **patch_scope** — описание области изменения (например один ключ, один список).
- **patch_status** — draft | validated | applied | failed | rolled_back.
- **diff_summary** — краткое текстовое описание изменения (для dry-run и отчёта).
- **validation_status** — ok | error; при error — validation_errors список.
- **backup_ref** — путь или идентификатор backup-файла до apply.
- **applied_at** — ISO timestamp применения.
- **applied_by** — actor (owner, web, telegram).
- **rollback_supported** — true/false; для safe append/add поддерживается откат по backup.

## Классификация по риску

- **Low risk (safe):** add_specialization_profile (добавление новой записи), append_specialization_keyword, append_routing_keyword, append_typical_request, add_alias, append_guardrail_note, update_summary_minor — только добавление или точечное дополнение без удаления и переименования.
- **High risk:** удаление ключей, переименование canonical keys, массовое изменение структуры, слияние/разделение профилей — не auto-applicable; только export и ручное применение.
