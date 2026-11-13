# Domain override and step-specific prompts — playbook (Phase 10.2)

## Как система подбирает domain context

- По тексту задачи выполняется domain triage (primary/secondary, context packs).
- Effective context = активный override (если есть) или результат авто-подбора.
- Для каждого шага workflow (pipeline, roundtable, court) из effective context строится **step-specific profile**: свой срез секций и лимит длины (pipeline: execution/methods ~800 символов, roundtable: viewpoints ~600, court: judgement/risk ~500).

## Чем отличаются pipeline / roundtable / court context

- **Pipeline** — фокус на исполнении: summary, strengths, typical_tasks, methods; чтобы агент шага понимал «как делать» в этом домене.
- **Roundtable** — фокус на обзоре и trade-offs: summary, strengths, typical_tasks; без дублирования полного execution context.
- **Court** — фокус на решениях и рисках: summary, strengths; кратко «в каком домене экспертизы задача и что это значит для решений».

## Как owner посмотреть effective domain

- **Telegram:** `/task_domain <id>` — текущий effective domain, override да/нет, подсказки (снять или изменить).
- **Dashboard:** страница задачи — блок «Экспертиза», при необходимости строка «Workflow context: &lt;domain&gt; / pipeline-focused. Court: risk emphasis».
- **Debug:** GET `/api/tasks/{id}/domain-context` — effective_domain_context, step_profiles, override_status, explainability.

## Как owner поставить override

- **Telegram:** `/set_task_domain <id> <domain_key> [причина]`. domain_key должен быть из registry (например legal, code).
- **Dashboard:** в карточке задачи — выпадающий список доменов, поле «причина» (необяз.), кнопка «Применить override».

## Как owner снять override

- **Telegram:** `/clear_task_domain <id>`.
- **Dashboard:** кнопка «Снять override» в блоке экспертизы (если override активен).

## Когда override нужен, а когда лучше не трогать

- **Нужен:** авто-подбор ошибся; задача явно в другом домене; нужно направить в конкретную экспертизу.
- **Лучше не трогать:** авто-подбор устраивает; нет уверенности в домене — можно оставить auto и при необходимости скорректировать позже.

## Как интерпретировать mismatch

- **Override mismatch** — авто-подбор дал домен A, owner задал домен B. Рекомендации могут показывать такой сигнал (override_mismatch_signal), чтобы owner видел задачи с ручной коррекцией домена.
- **Manual domain correction** — по задаче установлен override; полезно для аналитики «какие домены чаще исправляют вручную».
