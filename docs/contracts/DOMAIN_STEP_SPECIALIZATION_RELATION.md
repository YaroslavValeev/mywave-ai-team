# Domain – step – specialization relation (Phase 10.4)

- **Domain** — эффективный домен экспертизы (effective primary), определяет предметный контекст и context pack (Phase 10.0–10.2).
- **Step** — workflow step (pipeline, roundtable, court), определяет срез domain context и тип активности.
- **Specialization** — execution profile для пары (domain, step): execution_focus, expected_output_type, guardrails. Выбирается по domain + step из реестра; при отсутствии совпадения — fallback (general_*).
- **Execution lane** — итоговый объект для шага: domain context + selected specialization; передаётся в pipeline/roundtable/court и участвует в сборке prompt/context.
- **Audit** — фиксируются выбор специализации и использование fallback.
- **Owner/debug visibility** — показ выбранной специализации и причины (компактно в task card/detail и в API /api/tasks/{id}/specialization-context).
