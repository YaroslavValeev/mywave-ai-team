# Project, role and domain relation (Phase 10.0)

Краткое различие трёх слоёв и как они пересекаются в triage и views.

---

## Определения

- **Project** = где идёт работа (группировка задач: по domain/task_type, по project_key). Определяет срез «проект» в портфеле и drill-down.
- **Role** = кто смотрит / кто делает (owner, operator, executor, reviewer). Определяет права и срезы данных (action center, views).
- **Domain (expertise)** = какая экспертиза нужна задаче (legal, programming_engineer, marketing и т.д.). Определяет контекст, подсказки и рекомендации; не определяет права.

---

## Почему эти три не равны друг другу

- Один **project** может содержать задачи из разных **expertise domains** (например проект «Продукт»: и код, и маркетинг, и юридические проверки).
- Один **role** (owner) работает с задачами из разных **projects** и **domains**.
- **Domain** не привязан к project и не привязан к role; он привязан к содержанию задачи (текст, запрос).

---

## Как пересекаются в triage и views

- **Triage:** по тексту задачи определяются routing domain (существующий), task_type и **expertise domain** (primary/secondary). Project_key выводится из domain/task_type или явной привязки.
- **Views:** owner видит задачи, сгруппированные по project; в карточке задачи видит **domain hint** (expertise domain + краткое why). Role определяет, какие действия доступны; domain hint только информирует.
- **Recommendations:** могут учитывать распределение по expertise domains (например «много задач в legal», «backlog по programming_engineer») без смешивания с project или role.

---

## Запрет смешивания

- Не объединять project, role и domain в одну сущность или один «тип» задачи.
- Permission = по role; группировка по проекту = по project; контекст и подсказки = по domain.
