# KB ↔ проекты — карта (2026-11-14)

Аудит на сервере: Site `/var/www/mywave`, Agents `/opt/mywave/ai-team`.

## 1. Что есть

| Контур | Путь | Статус |
|--------|------|--------|
| Chat KB v2 (Wave 1) | `knowledge_base/chat/{boat,gym,booking,brand,_meta}/` | **Работает** — FAQ чата |
| Chat KB Wave 2 | `chat/{services,products,projects,social}/` | **Пусто** (только `.gitkeep`) |
| Project snippets | `knowledge_base/projects/*.txt` | **5 файлов** (Safari/Challenge/Ruza) |
| Legacy tips | `knowledge_base/wakesurfing_tips.txt/` | ~30 файлов, fallback |
| Rules/PDF/tricks | `training_methods.pdf/`, `tricks.*`, `training_data.jsonl` | Справочник, не Chat KB v2 |
| Agents intake | `/opt/mywave/ai-team/app/knowledge_intake/` | Owner drafts → approve → memory |
| Offsite backups | `/opt/mywave/knowledge-backups/` | tar.gz снимки KB |
| shared-core MemoryEntry | umbrella packages | Целевой SoT, **не заменяет** Site KB |

Site HEAD (prod): `36e61690`.

## 2. Связь с проектами (факт)

- Чат тянет проектные ответы из `knowledge_base/projects/*.txt` (legacy path в `responses_api`).
- CTA к проектам: `project_challenge` → `/projects/wakesurf-challenge-2025`, `project_safari` → `/projects/wakesurf-safari` (`chat/_meta/cta_buttons.md`).
- `brand/competitions.md` ссылается на `projects/wake_challenge.txt`.
- `chat/projects/` (Wave 2 MD) **не заполнен** — проектный слой в Chat KB v2 ещё не перенесён.
- Spot Map / FVLS / Event App / AGM **не читают** Site Chat KB.

### Project files

| Файл | Строк | Заметка |
|------|------:|---------|
| `mywave_ruza_camp.txt` | 11 | Ruza Camp |
| `wake_challenge.txt` | 7 | короткий |
| `wakesurf_challenge.txt` | 27 | дубль/расширение Challenge |
| `wake_surf_safari.txt` | 28 | Safari |
| `wakesurf_safari.txt` | 9 | дубль Safari (короткий) |

Риск: два Safari и два Challenge → расхождение ответов чата.

## 3. Как пользоваться (Owner)

1. Редактура FAQ: правьте MD в `knowledge_base/chat/{boat,gym,booking,brand}/`.
2. Шаблон и правила: `docs/integration/KNOWLEDGE_BASE_AUTHORING_GUIDE.md`.
3. Routing: `knowledge_base/chat/_meta/routing_rules.md`.
4. Проектный one-pager: правьте/добавляйте `knowledge_base/projects/<slug>.txt` (пока так; Wave 2 MD — позже).
5. Цены — только из `configs/services.yaml`, не из памяти.
6. Проверка: `pytest tests/unit/test_knowledge_base_v2.py tests/integration/test_chat_kb_answers.py -q`.
7. Знания для Agents/Owner memory — через `knowledge_intake` (draft → approve), не через правку chat MD.

## 4. Рекомендуемые следующие шаги

1. Свести дубли Safari/Challenge к одному canonical файлу на проект.
2. Заполнить Wave 2 `chat/projects/` MD по Authoring Guide (или явно отложить).
3. Не смешивать Site KB и Agents intake без bridge-контракта.
4. Отдельный PR: health/commit_sha в AGM (не KB).

## 5. Критерий готовности этой задачи

- [x] Карта контуров KB зафиксирована
- [x] Связь с проектами MyWave описана
- [x] Инструкция Owner указана
- [x] Owner выбрал: чистить дубли projects/*.txt (Site PR #125)
- [ ] Wave 2 chat/projects/ — отложено (опционально)
- [x] Boundary Site KB ↔ Agents intake: docs/contracts/SITE_KB_AGENTS_INTAKE_BOUNDARY.md
