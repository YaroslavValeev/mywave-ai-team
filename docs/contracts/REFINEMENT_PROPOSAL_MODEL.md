# Refinement proposal model (Phase 10.6)

## Поля

- **proposal_id** — уникальный идентификатор (например short uuid).
- **proposal_type** — тип предложения: `add_specialization_profile`, `expand_specialization_profile`, `adjust_routing_keywords`, `add_alias`, `review_domain_mapping`, `tighten_fallback_rule`.
- **target_layer** — куда направлено изменение: `domain_registry`, `domain_aliases`, `specializations`.
- **target_key** — ключ в целевом слое (domain_key, alias, specialization_key и т.д.).
- **reason** — краткое объяснение (1–2 предложения).
- **evidence_summary** — сводка доказательств (counts, window, source).
- **recommended_change** — что рекомендуется сделать (текст или код действия).
- **source_signals** — список signal_type / refinement_item_key, из которых сгенерировано предложение.
- **severity** — `low` | `medium`.
- **status** — `proposed` | `reviewed` | `accepted` | `rejected` | `applied`.
- **created_at** — ISO timestamp создания.
- **reviewed_at** — ISO timestamp ревью (если было).
- **applied_at** — ISO timestamp применения (если было).
- **reviewer** — идентификатор reviewer (owner, web, telegram).
- **notes** — произвольные заметки при review/apply.

## Примеры proposal_type

- `add_specialization_profile` — добавить профиль для пары (domain, step).
- `expand_specialization_profile` — расширить существующий профиль (keywords, guardrails).
- `adjust_routing_keywords` — скорректировать ключевые слова в domain registry.
- `add_alias` — добавить алиас для домена.
- `review_domain_mapping` — провести ручной обзор маппинга домена/проекта.
- `tighten_fallback_rule` — уточнить правило fallback (документально или в конфиге).

## Связь с backlog

Proposal создаётся из элемента refinement backlog (или из refinement signals); source_signals и evidence_summary связывают proposal с аналитикой.
