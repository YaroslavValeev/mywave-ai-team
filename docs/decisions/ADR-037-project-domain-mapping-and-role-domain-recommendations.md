# ADR-037: Project–domain mapping and role-domain recommendations

## Контекст

После Phase 10.2 доменный контекст встроен в task/workflow и override, но слой project и role недостаточно используют domain intelligence: нет project-level domain picture, cross-project доменной карты, role-specific domain recommendations, понимания project–domain mismatch.

## Решение

Вводится baseline:

- **Project–domain mapping** — по активным/недавним задачам проекта (project_key) считаем dominant expertise domain и distribution; explainable rule-based.
- **Dominant domain summary by project** — какой домен экспертизы доминирует в проекте и почему (по задачам).
- **Mismatch signals** — override-heavy project, расхождение между группировкой проекта и dominant expertise domain.
- **Role–domain recommendations** — для owner, operator, executor, reviewer: какие домены сейчас важны, зачем роли, что делать, на чём основано.
- **Domain-aware role views** — усиление существующих role views доменными рекомендациями и pressure.
- **Explainable relation** project ↔ domain ↔ role: проект = где идёт работа, domain = какая экспертиза доминирует/нужна, role = кто смотрит/действует.

## Границы

- Project, role и domain остаются разными слоями; domain signals advisory.
- Role permissions не зависят напрямую от domain.
- Project–domain mapping не меняет canonical workflow lifecycle (Run / Approval / Event / Artifact).

## Non-goals

- Не строить тяжёлую project ontology.
- Не делать hard assignment engine «кто должен работать».
- Не делать opaque multi-factor scoring.
- Не ломать существующие project/role views.
