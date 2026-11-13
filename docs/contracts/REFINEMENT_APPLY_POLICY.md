# Refinement apply policy (Phase 10.6)

## Что можно применять на этом этапе

- **add alias** — добавление алиаса для домена в конфигурацию/реестр (если есть безопасный API или файл алиасов).
- **adjust routing keywords** — точечное дополнение ключевых слов в domain registry (при наличии формата patch).
- **enable additional specialization entry** — добавление новой записи в specializations.yaml по шаблону (domain_key, workflow_step, summary, execution_focus и т.д.).
- **update specialization summary/keywords** — обновление существующей записи (summary, selection_keywords) без смены структуры.
- **mark registry item for manual review** — не изменение файла, а создание экспортированного кандидата (patch/candidate) для ручного применения; считаем «применением» в смысле workflow после того, как owner вручную внёс изменение и отметил proposal как applied.

## Что нельзя применять автоматически

- Крупные структурные изменения реестров (переименование ключей, слияние доменов).
- Массовое переписывание registry.
- Глубокое изменение project/domain model или схемы БД.

## Реализация apply baseline

- **Вариант A:** apply только меняет статус proposal на `applied` и пишет audit; фактическое изменение реестра owner делает вручную по экспортированному candidate. Тогда «apply» = «отметить как применённое после ручной правки».
- **Вариант B:** для подмножества безопасных типов (например add_specialization_profile с фиксированным шаблоном) реализовать запись в YAML/JSON; для остальных — только export.
- На этапе 10.6 допустимо реализовать **вариант A** везде: export_refinement_proposal / build_registry_patch_candidate дают human-readable и machine-readable кандидат; mark_refinement_proposal_applied фиксирует факт применения и пишет audit. Автозапись в файлы реестров — опционально и только для явно оговорённых безопасных операций.
