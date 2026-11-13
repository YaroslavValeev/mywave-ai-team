# Task-domain persistence baseline (Phase 10.0)

Где и как хранится expertise domain metadata, связь с TaskRepository.

---

## Варианты хранения

1. **Compute on read** — metadata не хранится; при запросе карточки задачи вызывается triage_domains_for_task(task.owner_text), результат возвращается в ответе. Плюс: без миграций и без дублирования. Минус: повторный расчёт при каждом чтении.
2. **JSON на задаче** — поле `domain_metadata_json` (nullable) в таблице tasks. Заполняется при triage (intake/pipeline). Плюс: один раз посчитали, читаем быстро. Минус: нужна миграция и обновление update_task.
3. **Отдельный store** — lightweight таблица или key-value по task_id. Аналогично (2), с разделением схемы.

---

## Рекомендация для Phase 10.0

- **Baseline:** compute on read. Сервис `task_domain_store` (или прямо в domain_triage) по task_id загружает task, берёт owner_text, вызывает triage_domains_for_task, возвращает metadata. Persistence не обязательна для приёмки этапа.
- **Опционально:** при наличии миграции добавить `domain_metadata_json` на Task и сохранять результат triage при intake; тогда при чтении использовать сохранённое или пересчитывать при отсутствии.

---

## Связь с TaskRepository

- TaskRepository не обязан знать про expertise domain; доменная metadata может поставляться отдельным сервисом (domain_triage / task_domain_store) по task_id или по task object.
- Если введено поле domain_metadata_json: update_task принимает domain_metadata_json; при triage после run_triage вызывается build_task_domain_metadata(owner_text), результат передаётся в update_task.

---

## Что хранится persistently (если добавлено поле)

- primary_domain, secondary_domains, domain_reason, matched_keywords, context_pack_keys, domain_confidence, domain_selection_source, domain_routing_version.

## Что вычисляется on read (baseline без поля)

- Всё перечисленное выше вычисляется при запросе карточки/списка, если не задано сохранённое значение.
