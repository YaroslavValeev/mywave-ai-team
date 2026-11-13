# TUNING_PATCHABILITY_HEURISTICS — Phase 11.3

Правила классификации tuning candidates для semi-automated safe path vs manual.

## Safe / low-risk (после accept + to-proposal)

- Кандидат с `candidate_type` **`expand_specialization_keywords`** (или сигнал частого fallback по domain/step) → proposal `expand_specialization_profile` → тот же путь, что `add_specialization_profile` в `build_registry_patch_candidate` → **add_entry** в specializations.yaml при отсутствии дубликата ключа.
- Планируемые мелкие правки реестра: **добавить keyword**, **guardrail note**, **typical request**, расширить **selection_keywords** — когда registry patch builder помечает тип как SAFE и есть валидный `target_file`.

## Manual-only

- **`adjust_execution_focus`** / радикальная смена execution_focus без шаблона safe delta.
- **`review_fallback_strategy`** / **`review_specialization_profile`** — требуют суждения owner.
- Изменение **canonical keys**, **слияние/разделение профилей**.
- Proposal тип **`adjust_routing_keywords`** с target `domain_registry or routing config` (нет безопасного файлового apply в Phase 10.7).
- Любой случай, когда `build_patch_candidate` возвращает `apply_allowed: false`.

## До конверсии (preview)

- `patchable: true` с оговоркой: «после accept и to-proposal ожидается safe add profile» для expand-кандидатов.
- `patchable: false` + `manual_only` для adjust_execution_focus и review-*.

## Верификация

- После apply — **обязательна** проверка outcome в окне N дней (рекомендация 14–30).
- Read-only метрики не требуют approve; запись в реестр — по существующему policy Phase 10.7.
