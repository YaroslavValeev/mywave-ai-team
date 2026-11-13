# TUNING_PATCH_MODEL — Phase 11.3

Модель связки tuning candidate с patch candidate (semi-automated path). Запись может быть **вычисляемой** (view-model) или отражать сохранённый trace в proposal/patch meta.

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `tuning_patch_id` | str | Стабильный id вида `tp_{tuning_candidate_id}` или `tp_{candidate_id}_{proposal_id}` |
| `tuning_candidate_id` | str | Связь с tuning store |
| `proposal_id` | str \| null | После `to-proposal` |
| `patch_id` | str \| null | Из `build_patch_candidate` после конверсии |
| `patchable` | bool | True если допустим safe/low-risk path (или уже есть apply_allowed patch) |
| `patchability_reason` | str | Человекочитаемое объяснение |
| `target_layer` | str | e.g. `specializations`, `domain_registry`, `manual` |
| `target_file` | str \| null | Путь к файлу или null если manual |
| `change_type` | str | См. ниже |
| `expected_effect` | str | Ожидаемый эффект на execution lane |
| `verification_required` | bool | Обычно true после apply |
| `status` | str | `preview`, `proposal_ready`, `patch_built`, `applied`, `manual_only`, `blocked` |
| `created_at` | str \| null | ISO |
| `applied_at` | str \| null | Из proposal или patch meta |
| `verified_at` | str \| null | Из outcome layer |

## change_type (примеры)

- `append_specialization_keyword` — низкий риск (после расширения builder)
- `append_guardrail_note`
- `append_typical_request`
- `expand_execution_focus_note`
- `small_profile_adjustment` — только если покрыто safe patch types
- `add_specialization_profile` — текущий safe apply (новая запись в YAML)
- `manual_only` — routing-only, структурные изменения, canonical keys

## Связи

- `tuning_candidate` 1 — 0..1 `refinement_proposal` (после convert)
- `refinement_proposal` 1 — 0..1 `patch_candidate` (Phase 10.7)
- `patch_candidate` 1 — 0..1 фактический apply в `registry_patches.json` meta
