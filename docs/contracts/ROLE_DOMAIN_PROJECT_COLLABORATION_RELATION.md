# Role – domain – project – collaboration relation (Phase 10.9)

- **Role** — кто действует: owner, reviewer, executor, operator. Определяет scope visibility и допустимые действия.
- **Domain** — какая экспертиза нужна для задачи. Влияет на routing, specialization, context.
- **Project** — где происходит работа (project_key = domain/task_type group). Агрегирует задачи, health, domain lifecycle.
- **Collaboration** — как роли связываются вокруг работы: handoff patterns, bottlenecks, cross-role recommendations. Четвёртый слой поверх role/domain/project.

Collaboration не смешивает три предыдущих: он использует role (кто), domain (какая экспертиза), project (где) как входные данные и добавляет «как роли взаимодействуют» — handoff readiness, blockers, recommended next role, collaboration hotspots.
