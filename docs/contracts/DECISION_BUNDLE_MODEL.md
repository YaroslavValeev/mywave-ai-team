# Decision bundle model (Phase 11.7)

## Decision bundle

| Поле | Описание |
|------|----------|
| `decision_bundle_id` | `db_<bundle_type>_<subject_key>` |
| `bundle_type` | `project_intervention_bundle` \| `portfolio_attention_bundle` \| `collaboration_resolution_bundle` \| `tuning_recovery_bundle` \| `cross_layer_conflict_bundle` |
| `subject_type` | `project` \| `portfolio` \| `task` \| `cross_layer` |
| `subject_key` | Ключ субъекта |
| `headline` | Заголовок bundle |
| `why_now` | Почему сейчас |
| `top_problem` | Главная проблема |
| `candidate_interventions` | Список intervention items |
| `preferred_sequence` | Упорядоченный список id preferred order |
| `do_now` | Первый шаг (intervention или summary) |
| `do_next` | Следующий шаг |
| `defer` | Что можно отложить |
| `evidence_summary` | Краткие evidence строки |
| `related_objects` | `[{type, id}]` — execution_id, tuning_candidate_id, task_id и т.д. |

## bundle_type — примеры

- **project_intervention_bundle** — проект нуждается во внимании owner
- **portfolio_attention_bundle** — portfolio-level priorities
- **collaboration_resolution_bundle** — collaboration bottleneck / execution follow-up
- **tuning_recovery_bundle** — tuning worse / patchable / follow-up
- **cross_layer_conflict_bundle** — collaboration improved + tuning worse
