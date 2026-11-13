# API_CONTRACTS

Контракты API между слоями (Product, Governance, Runtime) и shared-core. Все операции с сущностями идут через shared-core; слои не обращаются к storage напрямую.

Ссылка: [ENTITY_CONTRACTS.md](ENTITY_CONTRACTS.md), [ADR-002](../decisions/ADR-002-source-of-truth.md).

---

## Принципы

1. **Единая точка входа:** все создание/чтение/обновление Task, Run, Decision, Approval, Artifact, MemoryEntry — через shared-core (repositories или service layer).
2. **ID только из shared-core:** task_id, run_id, decision_id, approval_id, artifact_id, memory_id, event_id выдаёт shared-core.
3. **Политика:** чтение routing/approval rules — из shared-policy; применение и запись решений — через shared-core.

---

## Product Layer → shared-core

| Операция | Метод/контракт | Кто инициирует | Примечание |
|----------|----------------|----------------|------------|
| Создать Project | `create_project(ProjectCreate)` → Project | Personal_Helper | project_id из shared-core |
| Создать Task | `create_task(TaskCreate)` → Task | Personal_Helper | task_id из shared-core; origin_channel обязателен |
| Прочитать Task | `get_task(task_id)` → Task | Personal_Helper | |
| Список Tasks по project | `list_tasks(project_id, filters?)` → list[Task] | Personal_Helper | |
| Читать MemoryEntry | `get_memory(project_id, scope, key)` / list | Personal_Helper | для KB/context |
| Читать Artifact | `get_artifact(artifact_id)` → Artifact | Personal_Helper | для отображения результата |
| Записать MemoryEntry | `upsert_memory(MemoryEntry)` | Personal_Helper | при пользовательском вводе/контексте |

Product Layer **не** создаёт Run, Decision, Approval; не обновляет status Task в run-фазу (это делает Governance/Runtime).

---

## Governance Layer → shared-core

| Операция | Метод/контракт | Кто инициирует | Примечание |
|----------|----------------|----------------|------------|
| Читать Task | `get_task(task_id)` → Task | Agents | |
| Обновить Task (triage, status) | `update_task(task_id, TaskUpdate)` | Agents | status: new → triaged, planned, in_run, wait_approval |
| Создать Decision | `create_decision(DecisionCreate)` → Decision | Agents | decision_id из shared-core |
| Создать Approval (запрос) | `create_approval(ApprovalCreate)` → Approval | Agents | при execute_gate по policy; approval_id из shared-core |
| Читать Approval | `get_approval(approval_id)` | Agents | |
| Читать Run | `get_run(run_id)` | Agents | для контекста review |
| Список Runs по task | `list_runs(task_id)` → list[Run] | Agents | |
| Читать MemoryEntry | `get_memory` / list | Agents | для контекста |
| Записать MemoryEntry | `upsert_memory` | Agents | при выводе governance |

Governance **не** создаёт Run (создаёт Molt); **не** генерирует task_id/run_id.

---

## Runtime Layer (Molt) → shared-core

| Операция | Метод/контракт | Кто инициирует | Примечание |
|----------|----------------|----------------|------------|
| Создать Run | `create_run(RunCreate)` → Run | Molt | run_id из shared-core; только Molt вызывает |
| Обновить Run | `update_run(run_id, RunUpdate)` | Molt | status, ended_at, error_summary |
| Читать Task | `get_task(task_id)` | Molt | |
| Обновить Task (status in_run) | `update_task(task_id, {status})` | Molt | при старте/окончании run |
| Создать Approval (запрос) | `create_approval(ApprovalCreate)` | Molt | при критическом действии по policy |
| Обновить Approval | только shared-core по сигналу owner | — | Molt только читает status |
| Читать Approval | `get_approval(approval_id)` | Molt | перед продолжением после waiting_approval |
| Создать ExecutionEvent | `append_event(ExecutionEventCreate)` | Molt | event_id из shared-core |
| Создать Artifact | `create_artifact(ArtifactCreate)` → Artifact | Molt | |
| Записать MemoryEntry | `upsert_memory` | Molt | при результатах выполнения |

Runtime **не** создаёт Task; **не** создаёт Decision (это Governance); создаёт Run только через shared-core и только от имени оркестратора.

---

## Чтение policy (все слои) → shared-policy

- **Routing:** загрузка routing.yaml (домены, task_types, pipeline, roundtable, execute_gate). Используют Governance и при необходимости Runtime.
- **Approval rules:** загрузка approval.yaml (approval_required_actions). Используют Governance и Runtime для проверки «требуется ли approval» перед действием.
- **Escalation:** загрузка escalation.yaml. По необходимости.

Слои **не** изменяют policy в runtime; изменение policy — деплой конфигов shared-policy.

---

## Обязательные поля при создании

- **TaskCreate:** project_id, title, description, priority, origin_channel (остальное может выставить core: task_id, status=new, created_at, updated_at).
- **RunCreate:** task_id, orchestrator (например "molt"); core выставляет run_id, status=created, started_at.
- **DecisionCreate:** task_id, decision_type, decision_value, created_by; core — decision_id, created_at.
- **ApprovalCreate:** task_id, scope (из approval_required_actions), status=requested, requested_at; опционально run_id, requested_by; core — approval_id.

Все контракты реализуются в shared-core (protocols + service_layer/repositories); данный документ — эталон для реализации и тестов.
