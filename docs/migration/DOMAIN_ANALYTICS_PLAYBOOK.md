# Domain analytics playbook (Phase 10.5)

## Как читать override analytics

- **Override summary**: за выбранное окно (по умолчанию 30 дней) показываются: сколько раз был установлен domain override (`domain_override`), сколько раз снят (`domain_override_cleared`), в скольких уникальных задачах был override, и rate (overrides / задачи с override).
- Источник: события в audit_events с типами `domain_override`, `domain_override_cleared`. Все числа объяснимы из подсчёта событий.

## Когда hotspot реально важен

- **Override hotspot (domain)**: домен, на который часто вручную переключают задачи (count >= 2 за окно). Важно, если owner стабильно правит авто-выбор в один и тот же домен — стоит проверить ключевые слова triage или алиасы для этого домена.
- **Override hotspot (project)**: «проект» (project_key = domain/task_type задачи), в котором много override. Важно, если в одной тематической группе задач владелец часто исправляет домен — возможно, нужен пресет домена для проекта или уточнение формулировок.
- Порог задаётся в коде (HOTSPOT_MIN_COUNT = 2). При малом объёме данных hotspot может не появиться — это нормально.

## Как интерпретировать fallback rates

- **Specialization fallback summary**: за окно считаются события `specialization_fallback_used` и `specialization_selected`. Fallback rate = fallback / (fallback + selected).
- Высокий fallback rate означает: часто для пары (domain, step) нет профиля в реестре и подставляется general_*. Это не ошибка, а сигнал к возможному расширению реестра специализаций для часто встречающихся пар домен+шаг.
- **Specialization hotspots**: пары (domain_key, workflow_step) с числом fallback >= 2. По ним можно целенаправленно добавлять или расширять профили.

## Что делать руками, а что не автоматизируется

- **Вручную**: изменение реестра доменов (keywords, алиасы), реестра специализаций (добавление/правка профилей для domain+step), разбор причин override по конкретным задачам.
- **Не автоматизируется на этом этапе**: авто-запись в registry, самообучающаяся подстройка, изменение policy без решения owner/GM. Analytics только подсказывает, где обратить внимание.
