# TUNING_TO_PATCH_TO_OUTCOME_RELATION — Phase 11.3

Цепочка traceability от сигнала до рекомендации.

## Путь

1. **Specialization signal** (`get_refinement_signals`) — override/fallback hotspots, unstable lane.
2. **Tuning candidate** (`generate_tuning_candidates`) — `tuning_candidate_id`, статусы review.
3. **Refinement proposal** (`convert_tuning_candidate_to_proposal`) — `source_tuning_candidate_id`, `proposal_id`.
4. **Patch candidate** (`build_patch_candidate(proposal_id)`) — `patch_id`, `apply_allowed`, `risk_level`.
5. **Apply** (`apply_patch_candidate`) — запись YAML, `registry_patches.json` meta, proposal `applied`.
6. **Baseline capture** (`record_tuning_baseline_on_patch_apply`) — fallback metrics по domain/step в момент apply.
7. **Outcome** (`evaluate_tuning_outcome`) — сравнение baseline vs текущие hotspots → `outcome_status`, `outcome_reason`.
8. **Recommendation / update** — `owner_recommendations`, при необходимости ручной verify (Phase 11.2).

## Идентификаторы

- Сигнал не имеет долгоживущего id; ключ совпадает с логикой `refinement_item_key` / hash candidate.
- Обратная связь: `proposal.source_tuning_candidate_id` → candidate; `outcome.proposal_id` → proposal.

## Не смешивать

- Generic refinement proposal без `source_tuning_candidate_id` может иметь patch outcome в Phase 10.7, но **tuning outcome store** приоритетно связывает записи с tuning candidate id при наличии поля в proposal.
