# Collaboration recommendation model (Phase 10.9)

## Поля

- **recommendation_id** — уникальный идентификатор (опционально).
- **source_role** — от кого ожидается действие или кто «держит» работу.
- **target_role** — кому передать или кого подключить.
- **project_key** — проект (если применимо).
- **domain_key** — домен (если применимо).
- **reason** — причина рекомендации.
- **recommended_action** — что сделать.
- **urgency** — high | medium | low.
- **evidence_summary** — краткое доказательство (счётчики, task_ids).
