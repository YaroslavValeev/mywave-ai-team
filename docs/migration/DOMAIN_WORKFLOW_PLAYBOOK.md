# Domain-aware workflow — playbook (Phase 10.1)

## Как выбирается домен автоматически

- При triage по тексту задачи вызывается доменный слой (domain triage).
- Определяются `primary_domain` и `secondary_domains` по ключевым словам и registry.
- Собирается **context pack** и **compact_context** для выбранного домена.
- Этот контекст сохраняется в metadata и передаётся в workflow как **workflow_domain_context**.

## Как owner видит effective domain

- **Telegram:** `/task <id>` — в карточке задачи выводится строка «Экспертиза: &lt;domain&gt;». Если установлен override — «Override: yes (owner)» и при необходимости причина.
- **Telegram:** `/task_domain <id>` — только effective domain и статус override.
- **Dashboard:** страница задачи `/tasks/{id}` — блок «Экспертиза» с указанием override, если есть.

## Как сделать override

- Команда: `/set_task_domain <id> <domain_key> [причина]`.
- Пример: `/set_task_domain 42 legal Проверка договора`.
- `domain_key` должен существовать в domain registry (например `legal`, `code`, `docs`).
- После установки override эффективный домен для задачи = указанный; compact_context пересобирается для этого домена.
- Override сохраняется в `domain_overrides.json` и логируется в audit (`domain_override`).

## Когда override нужен

- Авто-подбор ошибся (задача про юриспруденцию, а система выбрала другой домен).
- Нужно явно направить задачу в другой домен экспертизы.
- Временная корректировка без изменения текста задачи.

## Как интерпретировать fallback

- Если домен не определён, в effective context будет `selected_primary_domain = None` или fallback.
- Workflow при отсутствии domain context продолжает работу без доменного блока; это допустимо и не ломает flow.

## Как domain context влияет на workflow

- После triage в `triage_result` попадает `workflow_domain_context` с полями `selected_primary_domain`, `compact_context`, `domain_override` и др.
- Pipeline добавляет в первый handoff секцию «Domain context (expertise)» с `compact_context`.
- Court добавляет в отчёт секцию «Domain context (expertise)».
- Рекомендации (domain-aware signals) группируют задачи по **effective** домену (с учётом override).

## Как не путать domain с policy/permission

- **Domain** — консультативный контекст исполнения (какая экспертиза/контекст подмешиваются в prompt).
- **Policy / permissions** — кто может approve, что разрешено делать, критические действия. Это отдельный слой.
- Override домена **не** меняет права доступа и не подменяет approve-правила.
