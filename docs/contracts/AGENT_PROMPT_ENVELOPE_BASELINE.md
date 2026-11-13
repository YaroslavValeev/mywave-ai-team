# Agent prompt envelope baseline (Phase 10.4)

Как в prompt/context попадают domain context и specialization profile.

## Разделение

- **Domain context** (Phase 10.2) — секция «Domain context (expertise)»: compact_context из domain_prompt_profiles (summary, strengths, typical_tasks по шагу). Источник: effective domain + step-specific slice.
- **Specialization** (Phase 10.4) — отдельная компактная секция или блок: execution_focus, expected_output_type, краткий список guardrails. Не дублирует compact_context; задаёт рамку «как выполнять» и «что на выходе».

## Где в prompt

- **Pipeline:** после (или перед) Domain context добавляется блок вида: «Execution: &lt;execution_focus&gt;. Expected output: &lt;expected_output_type&gt;. Guardrails: &lt;кратко&gt;.» Ограничение длины: ~300–400 символов на блок specialization.
- **Roundtable / Court:** аналогично — свой execution_focus и expected_output_type для шага; guardrails при необходимости сокращённо.

## Избежание bloat

- Не включать полный summary профиля в каждый handoff; достаточно execution_focus + expected_output_type + до 3 guardrails.
- Domain context остаётся основным носителем предметного контекста; specialization — только рамка исполнения и ограничения.
