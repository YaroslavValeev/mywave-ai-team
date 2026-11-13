# Registry validation baseline (Phase 10.7)

## Что проверяем

- **YAML/JSON parse** — файл должен корректно парситься после предполагаемого изменения (проверка на dry-run: смоделировать результат и распарсить).
- **Структура (schema-ish):** для specializations — наличие ключа specializations, значения — словари с полями specialization_key, domain_key, workflow_step; для domain_registry — domains, вложенные объекты с routing_keywords (список), typical_requests (список), aliases (список).
- **Дубликаты:** при добавлении новой записи в specializations — ключ не должен уже существовать; при append в aliases/routing_keywords — по желанию проверять дубликат значения (не обязательно блокировать, можно предупреждение).
- **Broken references:** при изменении domain_key или specialization_key не ломать ссылки (для safe types мы только добавляем, не переименовываем).

## Реализация

- **registry_validation.py:** validate_yaml_file(path) — парсинг, возврат ok/error и список ошибок; validate_specializations_structure(data) — проверка наличия specializations и структуры записей; validate_domain_registry_structure(data) — проверка domains; check_duplicate_specialization_key(data, key) — true если ключ уже есть. Для dry-run и apply вызывать валидацию после построения «нового» содержимого в памяти.
