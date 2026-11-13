# Domain registry model (Phase 9.9)

Формализация записей реестра доменов экспертизы. Registry — слой над файлами know_proff, не замена им.

---

## Поля записи домена

| Поле | Описание |
|------|----------|
| **domain_key** | Уникальный идентификатор (snake_case), используется в API и routing. |
| **canonical_name** | Человекочитаемое название домена. |
| **current_source_file** | Имя файла в docs/know_proff (например layer.txt). |
| **structure_type** | A (10 разделов) или B (тематические блоки). |
| **description** | Краткое описание домена (1–3 предложения). |
| **core_skills** | Ключевые навыки (список строк). |
| **typical_tasks** | Типовые задачи/запросы (список). |
| **tools** | Инструменты (список). |
| **interaction_patterns** | Как домен взаимодействует с другими функциями (кратко). |
| **training_value** | Ценность для онбординга/обучения (кратко). |
| **routing_keywords** | Ключевые слова для сопоставления задачи с доменом. |
| **routing_signals** | Дополнительные сигналы (фразы, паттерны). |
| **fallback_priority** | Приоритет при fallback (число; меньше = выше приоритет). |

---

## Дополнительные поля в machine-readable registry

- **aliases** — список альтернативных имён и опечаток (например programming ingeneer → programming_engineer).
- **summary** — краткое содержание для карточки.
- **typical_requests** — примеры типичных запросов/задач в свободной форме.
- **notes** — примечания (степень готовности к routing, ограничения).

---

## Mapping: файл → домен

| source_file | domain_key | canonical_name | structure_type |
|-------------|------------|----------------|----------------|
| layer.txt | legal | Юридический отдел | A |
| Analiz.txt | analytics | Аналитика данных | A |
| Creating.txt | development | Разработка (стратегия, креатив) | A |
| Programming ingeneer.txt | programming_engineer | Программирование и анализ кода | A |
| Financ.txt | finance | Финансы и бухгалтерия | A |
| Sociol media.txt | social_media | Социальные медиа | A |
| Brand manager.txt | brand_manager | Бренд-менеджмент | B |
| Copiwriter.txt | copywriting | Копирайтинг | B |
| marketing.txt | marketing | Маркетинг | B |
| Sales.txt | sales | Продажи | B |
| Smm.txt | smm | SMM | B |
| Social ingeneer.txt | social_engineering | Социальная инженерия (безопасность) | B |

---

## Требование

Для каждого файла из docs/know_proff в реестре должна быть ровно одна запись с указанным source_file и domain_key. Степень готовности к routing может различаться (notes).
