# Project binding model (Phase 9.5)

Практичный контракт привязки задач к проектам без отдельной project entity в БД. Модель честная и explainable.

---

## Минимальные понятия

### project_key

Строковый идентификатор группы. Источники (по приоритету):

1. **task.domain** — если заполнен (после triage/pipeline).
2. **task.task_type** — если domain пуст.
3. **fallback_group** — иначе `"general"`.

Итог: `project_key = (task.domain or task.task_type or "general").strip() or "general"`.

### project_label

Человекочитаемое имя группы. В baseline: равно `project_key`. При появлении явной project entity можно заменить на имя из справочника.

### binding_source

Откуда взят ключ для задачи:
- `"domain"` — из task.domain;
- `"task_type"` — из task.task_type;
- `"fallback"` — использована группа general.

Используется для объяснимости, не обязательно показывать в UI.

### binding_confidence

В baseline не вычисляется отдельно. Можно считать: явный domain = выше уверенность; fallback = ниже. Пока не обязательное поле.

### fallback_group

Константа `"general"`. Все задачи без domain и task_type попадают в эту группу.

---

## Как task попадает в project group

1. Для каждой задачи вычисляется `project_key` по правилу выше.
2. Одна задача принадлежит ровно одной группе в baseline (нет множественной привязки).
3. Список проектов = множество уникальных `project_key` по всем задачам. Если задач нет, можно показывать хотя бы `["general"]`, чтобы был вход в drill-down.

---

## Обработка ambiguous / unknown

- Задачи без domain и task_type → `project_key = "general"`.
- Пустые строки после strip → `"general"`.
- Нет отдельной сущности «неизвестный проект»: всё, что не удалось отнести, в `general`.

---

## Ограничения (честная модель)

- Это не идеальная project entity model: нет отдельной таблицы projects, нет иерархии, нет многих-ко-многим.
- Одна задача в baseline привязана к одной группе.
- При появлении явного поля `task.project_id` или справочника проектов baseline можно заменить, сохранив контракт project_key/label для owner-facing слоя.
