# Domain step context policy (Phase 10.2)

Правила отбора и ограничения контекста по шагам workflow.

## Pipeline

- **Секции:** summary, strengths, typical_tasks, methods (если есть). Не включать interaction_style / not_for в основной блок.
- **Длина:** compact_context до ~800 символов.
- **Фокус:** execution, методы, типичные задачи — чтобы агент шага ориентировался на «как делать», а не на обсуждение.

## Roundtable

- **Секции:** summary, strengths, typical_tasks; можно кратко trade-offs (из summary или одной фразой).
- **Длина:** до ~600 символов.
- **Фокус:** viewpoints, collaboration, что важно учесть при обзоре — без дублирования полного execution context.

## Court

- **Секции:** summary, strengths; при необходимости одна фраза по risk/compliance из summary.
- **Длина:** до ~500 символов.
- **Фокус:** judgement, decision rationale, risk framing — кратко «в каком домене экспертизы задача и что это значит для решений».

## Общие правила

- Контекст должен становиться **более точным** по шагу, а не более длинным.
- Один и тот же compact_context не вставляется одинаково во все шаги: каждый шаг получает свой срез (included_sections) и лимит длины.
- Primary/secondary domains на каждом шаге берутся из effective domain context (override или auto); не переопределяются отдельно по шагу.
