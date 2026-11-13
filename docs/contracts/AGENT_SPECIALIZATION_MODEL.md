# Agent specialization model (Phase 10.4)

Профиль специализации агентного шага: какой execution focus, стиль и ограничения применять для пары (domain, workflow_step).

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `specialization_key` | string | Уникальный ключ профиля (например legal_pipeline_analysis) |
| `domain_key` | string | Домен экспертизы (legal, programming_engineer, finance, …) |
| `workflow_step` | string | pipeline \| roundtable \| court |
| `profile_name` | string | Человекочитаемое имя |
| `summary` | string | Краткое описание |
| `execution_focus` | string | На чём фокус шага (analysis, trade-offs, judgement, …) |
| `style` | string | Стиль работы (structured, exploratory, review, …) |
| `expected_output_type` | string | Ожидаемый тип выхода (analysis_report, risk_table, decision_rationale, …) |
| `recommended_methods` | list[string] | Рекомендуемые методы (опционально) |
| `guardrails` | list[string] | Ограничения / что не делать |
| `signal_keywords` | list[string] | Ключевые слова для уточнения выбора (опционально) |
| `selection_reason` | string | Почему выбран (заполняется при выборе) |

## Baseline-профили (примеры)

- **legal_pipeline_analysis** — domain=legal, step=pipeline: анализ договоров/условий, структурированный вывод.
- **legal_court_decision** — domain=legal, step=court: обоснование решения, риски, compliance.
- **finance_pipeline_check** — domain=finance, step=pipeline: проверка цифр, допущений, отчётность.
- **programming_pipeline_execution** — domain=programming_engineer, step=pipeline: выполнение, методы, инструменты.
- **programming_roundtable_tradeoffs** — domain=programming_engineer, step=roundtable: trade-offs, альтернативы, ревью.
- **general_pipeline**, **general_roundtable**, **general_court** — fallback при отсутствии доменного совпадения.

Мало профилей, но ясных и explainable.
