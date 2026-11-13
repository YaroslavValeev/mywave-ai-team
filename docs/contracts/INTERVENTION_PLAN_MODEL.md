# Intervention plan model (Phase 11.7)

## Plan (scope-level)

| Поле | Описание |
|------|----------|
| `plan_id` | Стабильный id: `ip_<scope_type>_<scope_key>` или `ip_portfolio`, `ip_cross_layer` |
| `scope_type` | `task` \| `project` \| `portfolio` \| `cross_layer` |
| `scope_key` | Ключ области (task_id, project_key) или пусто для portfolio/cross_layer |
| `plan_headline` | Краткий заголовок плана |
| `plan_reason` | Почему этот план |
| `priority_label` | `high` \| `medium` \| `low` |
| `interventions` | Список intervention items |
| `preferred_intervention` | Индекс или id preferred item |
| `fallback_intervention` | Индекс или id fallback |
| `expected_effect` | Ожидаемый эффект при выполнении |
| `risk_if_ignored` | Риск при игнорировании |
| `evidence_refs` | `[{id_type, id_value}]` для трассировки |
| `generated_at` | ISO timestamp (on-demand) |

## Intervention item

| Поле | Описание |
|------|----------|
| `intervention_id` | `iv_<scope>_<index>` |
| `intervention_type` | `approval` \| `collaboration_execution` \| `tuning_review` \| `tuning_patch` \| `refinement_review` \| `owner_attention` \| `runtime_escalation` и т.д. |
| `target_layer` | `product` \| `governance` \| `runtime` (соответствие канону) |
| `target_role` | `owner` \| `operator` \| `executor` \| `reviewer` |
| `safe_action_available` | bool |
| `safe_action_key` | Ключ action_center, если есть |
| `manual_path_required` | bool — нужен ручной путь, нет safe action |
| `reason` | Почему это вмешательство |
| `expected_effect` | Ожидаемый результат |
| `urgency` | `high` \| `medium` \| `low` |
| `execution_id` | Если связан с collaboration execution |
| `suggestion_id` | Если связан с suggestion |
