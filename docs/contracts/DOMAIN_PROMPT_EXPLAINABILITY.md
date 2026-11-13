# Domain prompt explainability (Phase 10.2)

Baseline объяснимости step-specific domain prompts.

## Что должно быть объяснимо

- **Почему этот step получил такой context** — выбран workflow_step и prompt_profile_key; selection_reason (override vs auto).
- **Какие sections включены** — included_sections в профиле.
- **Какие sections опущены** — excluded_sections или явное перечисление «не включено».
- **Почему выбран primary/secondary domain** — из effective domain context (override_reason или auto reason).

## Как owner/debug может это увидеть

- **Без перегруза основной карточки:** в task detail — компактная строка вида «Workflow context: &lt;domain&gt; / pipeline-focused» и при необходимости «Court context: risk/compliance emphasis»; либо в expandable/debug sub-block.
- **Debug endpoint:** GET `/api/tasks/{id}/domain-context` возвращает effective_domain_context, step-specific prompt profiles (pipeline, roundtable, court), override status, selection_reason, included_sections/excluded_sections в машиночитаемом виде.

## Ограничение

Не выводить полный текст prompt в UI; только метаданные и краткий фокус (step_specific_focus, selection_reason).
