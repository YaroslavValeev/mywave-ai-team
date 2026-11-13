# Project–domain playbook (Phase 10.3)

## Как читать dominant domain проекта

- **Проект** здесь = группа задач по project_key (task.domain / task_type / general).
- **Dominant domain** = домен экспертизы (effective primary_domain), у которого максимальное число активных задач в этой группе.
- В карточке проекта (/project <key>, Dashboard → проект): блок «Domain (expertise)» — доминирующий домен, при необходимости secondary, распределение по задачам.
- В списке проектов (/projects): у каждого проекта выводится dominant_domain при наличии.

## Когда mismatch важен

- **override_heavy** — в проекте ≥2 задач с ручным override домена → «много ручных правок домена».
- **correction_rate** — доля задач с override среди активных > 30% → «высокий процент ручной коррекции».
- Эти сигналы показываются в карточке проекта и попадают в project_domain_signals в рекомендациях.

## Как owner смотрит project-domain signals

- **Telegram:** /projects — в каждой строке dom: &lt;key&gt;; /project &lt;key&gt; — блок «Доминирующий домен» и «Сигналы» при mismatch; /project_domain &lt;key&gt; — полный domain profile.
- **Dashboard:** страница проекта — секция «Domain (expertise)» с dominant, secondary и mismatch.
- **Рекомендации:** get_domain_aware_signals возвращает project_domain_signals — список проектов с mismatch (override_heavy, correction_rate).

## Как не путать с role permissions

- Domain expertise и project-domain mapping — консультативные: подсказывают, где какая экспертиза и где много правок.
- Права (кто может approve, кто operator) не зависят от домена; домен только усиливает фокус рекомендаций.
