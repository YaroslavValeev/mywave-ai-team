# Role–domain playbook (Phase 10.3)

## Как role views используют domain recommendations

- **Owner:** домены с backlog (pending approvals), rework и ручными override → «Domain focus: X, Y» в /view_owner; рекомендация разобрать approvals/rework по приоритетным доменам.
- **Operator:** домены, где сконцентрированы блокеры и long-running → «Domain pressure: X» в /view_operator; рекомендация проверить runtime/логи по этим доменам.
- **Executor:** домены с наибольшим числом активных задач → «Domain focus: X» в /view_executor.
- **Reviewer:** домены, где сконцентрированы pending approvals и decision queue → «Domain focus: X» в /view_reviewer.

## Команды

- **/role_domains** — рекомендации по доменам для всех четырёх ролей (owner, operator, executor, reviewer).
- **/domain_pressure** — сводка domain pressure по ролям (кратко: какой домен важен для какой роли и почему).

## Как не путать role permissions и domain expertise

- **Permissions** — кто что может делать (approve, execute, view). Не зависят от домена.
- **Domain expertise** — консультативный слой: «на какие домены этой роли стоит обратить внимание сейчас» и «почему» (evidence: количество задач, approvals, блокеров и т.д.).
