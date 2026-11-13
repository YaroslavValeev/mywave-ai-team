# Registry tuning playbook (Phase 10.6)

## Связь analytics → proposals → tuning

- Аналитика (override hotspots, specialization fallback) даёт refinement signals и backlog.
- Backlog превращается в refinement proposals (предложения на изменение).
- Owner ревьюит и принимает/отклоняет; принятые можно применить.
- **Tuning** — это внесение изменений в domain registry и/or specialization registry на основе принятых предложений.

## Domain registry

- **Файлы:** domain registry (например app/data/domain_registry/), routing/keywords, алиасы.
- **Безопасные изменения:** добавление алиаса, дополнение ключевых слов для существующего домена. Массовое переименование или смена структуры — только вручную с контролем.
- **После apply:** при следующем прогоне triage и get_effective_domain_context новые ключевые слова/алиасы учтутся; можно проверить через /route или по задачам.

## Specialization registry

- **Файл:** app/data/agent_specializations/specializations.yaml.
- **Безопасные изменения:** добавление новой записи для пары (domain_key, workflow_step) по шаблону из export (yaml_suggestion); точечное обновление summary, selection_keywords, guardrails у существующей записи.
- **После apply:** при следующем запуске pipeline/roundtable/court для задач с этим доменом и шагом будет выбран новый профиль вместо general_*; fallback rate по этому hotspot может снизиться.

## Что не делать

- Не менять реестры автоматически без явного действия owner (нет self-healing).
- Не переписывать большие куски YAML без ревью.
- Не смешивать tuning с исполнением задач: реестры читаются в runtime, но запись в них — только через refinement workflow или ручное редактирование.
