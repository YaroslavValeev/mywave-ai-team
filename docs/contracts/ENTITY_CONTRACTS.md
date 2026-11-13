# ENTITY_CONTRACTS

Канонические поля сущностей, допустимые статусы и обязательность полей. Все слои и shared-core обязаны соблюдать эти контракты.

Ссылка: [DOMAIN_MODEL.md](../architecture/DOMAIN_MODEL.md), [shared-schema](../../packages/shared-schema/).

---

## Project

| Поле | Обязательно | Тип | Описание |
|------|-------------|-----|----------|
| project_id | да | string | Уникальный ID; генерируется shared-core |
| name | да | string | |
| slug | да | string | |
| status | да | enum | см. ниже |
| owner_id | да | string | |
| created_at | да | datetime | |
| updated_at | да | datetime | |
| description, goals, constraints, priority, stage, tags | нет | — | |

**Allowed statuses:** `draft` | `active` | `paused` | `archived`

**Owner:** shared-core. Создаёт Product Layer через shared-core.

---

## Task

| Поле | Обязательно | Тип | Описание |
|------|-------------|-----|----------|
| task_id | да | string | Уникальный ID; генерируется только shared-core |
| project_id | да | string | |
| title | да | string | |
| description | да | string | |
| status | да | enum | см. ниже |
| priority | да | string | |
| origin_channel | да | string | telegram \| cursor \| web \| desktop \| api |
| created_at | да | datetime | |
| updated_at | да | datetime | |
| task_type, requested_by, assigned_layer, risk_level, approval_required, parent_task_id | нет | — | |

**Allowed statuses:** `new` | `triaged` | `planned` | `in_run` | `wait_approval` | `done` | `failed` | `cancelled`

**Owner:** shared-core. Создаёт Product Layer. Обновляют Governance (triage, status), Runtime (status при run).

---

## Run

| Поле | Обязательно | Тип | Описание |
|------|-------------|-----|----------|
| run_id | да | string | Уникальный ID; генерируется только shared-core по запросу Molt |
| task_id | да | string | |
| orchestrator | да | string | Идентификатор оркестратора (Molt) |
| status | да | enum | см. ниже |
| started_at | да | datetime | |
| ended_at, executor, attempt, trace_id, error_summary | нет | — | |

**Allowed statuses:** `created` | `queued` | `running` | `waiting_approval` | `resumed` | `succeeded` | `failed` | `cancelled`

**Owner:** shared-core. Создаёт и обновляет только Molt через shared-core.

---

## Decision

| Поле | Обязательно | Тип | Описание |
|------|-------------|-----|----------|
| decision_id | да | string | Генерируется shared-core |
| task_id | да | string | |
| decision_type | да | string | |
| decision_value | да | enum | см. ниже |
| created_at | да | datetime | |
| created_by | да | string | |
| reasoning_summary, linked_run_id, requires_owner_approval, supersedes_decision_id | нет | — | |

**Allowed decision_value:** `proposed` | `accepted` | `rejected` | `superseded`

**Owner:** shared-core. Создаёт Governance Layer (Agents).

---

## Approval

| Поле | Обязательно | Тип | Описание |
|------|-------------|-----|----------|
| approval_id | да | string | Генерируется shared-core |
| task_id | да | string | |
| scope | да | string | Должен совпадать с scope из shared-policy approval_required_actions |
| status | да | enum | см. ниже |
| requested_at | да | datetime | |
| run_id, requested_by, approved_by, approved_at, comment | нет | — | |

**Allowed statuses:** `required` | `requested` | `approved` | `rejected` | `expired`

**Owner:** shared-core. Создаёт Governance или Runtime при обнаружении критического действия. Обновляет status только owner (через Telegram по MVP). Scope должен быть из списка approval_required_actions в shared-policy.

---

## Artifact

| Поле | Обязательно | Тип |
|------|-------------|-----|
| artifact_id | да | string |
| task_id | да | string |
| artifact_type | да | string |
| storage_uri | да | string |
| created_at | да | datetime |
| run_id, checksum, mime_type, title, preview | нет | — |

**Owner:** shared-core. Создаёт Runtime или Governance.

---

## MemoryEntry

| Поле | Обязательно | Тип |
|------|-------------|-----|
| memory_id | да | string |
| project_id | да | string |
| scope | да | string |
| key | да | string |
| value | да | string или dict |
| updated_at | да | datetime |
| source, confidence, ttl, linked_task_id, linked_artifact_id | нет | — |

**Owner:** shared-core. Создаёт/обновляет любой слой через shared-core.

---

## ExecutionEvent

| Поле | Обязательно | Тип |
|------|-------------|-----|
| event_id | да | string |
| run_id | да | string |
| event_type | да | string |
| timestamp | да | datetime |
| task_id, actor, payload, trace_id | нет | — |

**Owner:** shared-core. Создаёт только Runtime (Molt). Immutable после создания.

---

## Правила

1. **task_id** и **run_id** создаются только фабриками в shared-core; никакой слой не генерирует их самостоятельно.
2. Все обязательные поля должны быть заполнены при создании сущности.
3. Статусы и enum-значения — только из списков выше; расширение только через ADR и обновление shared-schema.
4. PolicyRule владеет shared-policy; остальные сущности — shared-core.
