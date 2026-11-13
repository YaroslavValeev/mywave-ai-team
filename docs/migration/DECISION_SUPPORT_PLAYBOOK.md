# DECISION_SUPPORT_PLAYBOOK — Phase 11.1

## Назначение

Playbook описывает, как использовать decision support. Decision support объединяет несколько suggestions в блок «что лучше сделать первым» с options, preferred_option и risk_if_ignored.

## Как читать decision support cards

### Поля

- **headline** — что требует решения.
- **why_now** — почему важно решить сейчас.
- **options** — варианты (label, description, action_hint).
- **preferred_option** — рекомендуемый вариант.
- **preferred_option_reason** — почему рекомендован.
- **risk_if_ignored** — что будет, если игнорировать.
- **evidence_items** — факты.

## Как owner/GM использовать decision support

1. **Портфель** — /owner/portfolio или /owner/decision-support: top collaboration actions, проекты, требующие внимания.
2. **Проект** — /owner/project/{key}: 1–3 suggestions по проекту.
3. **Роль** — /views/operator, /views/executor, /views/reviewer: role-specific suggestions.
4. **Telegram** — /decision_support, /suggestions, /project_suggestions, /role_suggestions.

## Scope types

- **portfolio** — cross-project decision support.
- **project** — scope_key = project_key.
- **task** — scope_key = task_id.
- **collaboration_hotspot** — по hotspots.
