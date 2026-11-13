# ADR-036: Agent-specific domain prompts and override UX

## Контекст

После Phase 10.1 domain-aware context уже участвует в workflow (effective context, compact_context в pipeline/court, owner override), но используется одинаково для всех шагов агентного процесса. Owner override UX минимален (только команды).

## Решение

Вводится:

- **Step-specific domain prompt/context profiles** — для pipeline, roundtable, court формируются разные по фокусу компактные контексты из одного effective domain (pipeline: execution/methods/tools; roundtable: viewpoints/trade-offs; court: judgement/risk).
- **Более явный prompt/context assembly** для workflow stages — сервис `domain_prompt_profiles` строит профиль под шаг; интеграция в pipeline/roundtable/court без замены существующего triage_result/workflow_domain_context.
- **Richer owner override UX** — сохранение `/set_task_domain` и `/task_domain`; добавление `/clear_task_domain`; в task detail — список доменов, apply/clear override; debug endpoint для domain context.
- **Explainable display** — текущий effective domain, override status, краткий step-specific usage summary (без перегруза основной карточки).

## Границы

- Domain prompt layer = advisory execution context; не заменяет canonical workflow semantics (Run / Approval / Event / Artifact).
- Owner override не меняет policy/permissions.
- Prompts остаются explainable и compact; не full know_proff в payload.

## Non-goals

- Не строить full prompt management platform.
- Не вводить black-box auto-prompting.
- Не делать heavy UI/CRUD вокруг доменов.
- Не хранить full know_proff внутри workflow payloads.
