# Project–domain–role triangle (Phase 10.3)

Краткая связь трёх слоёв.

- **Project** = где идёт работа: группировка задач по project_key (сейчас = task.domain / task_type / general). Сводки по здоровью, pending, rework, артефакты.
- **Domain** = какая экспертиза доминирует или нужна: effective primary_domain по задачам (legal, programming_engineer, …). Определяется по тексту задачи и override; участвует в workflow и рекомендациях.
- **Role** = кто смотрит/действует: owner, operator, executor, reviewer. У каждой роли свой срез данных (approvals, blockers, active tasks, decision queue).

## Связи

- **Project ↔ domain:** у проекта есть dominant_domain и distribution по задачам проекта; возможен mismatch (например много override в проекте).
- **Domain ↔ role:** роли получают domain recommendations — на какие домены обратить внимание и почему (owner — backlog/rework по доменам; reviewer — approvals по доменам; и т.д.).
- **Project ↔ role:** существующие role views уже агрегируют по проектам/задачам; domain layer добавляет «какой домен важен для этой роли сейчас».

## Где не совпадают

- Project_key (routing/grouping) может не совпадать с dominant expertise domain проекта — тогда даём сигнал «фактическая экспертиза — X».
- Role permission и domain expertise не смешиваем: права не зависят от домена; домен только советует фокус внимания.
