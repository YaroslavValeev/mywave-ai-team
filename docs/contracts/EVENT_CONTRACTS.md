# EVENT_CONTRACTS

Обязательные и допустимые события execution lifecycle. События пишутся в shared-core как ExecutionEvent; создаёт только Runtime (Molt).

Ссылка: [ENTITY_CONTRACTS.md](ENTITY_CONTRACTS.md), [ORCHESTRATION_MODEL.md](../architecture/ORCHESTRATION_MODEL.md).

---

## Сущность ExecutionEvent

- **event_id** — из shared-core.
- **run_id** — обязательно; событие привязано к Run.
- **event_type** — строка из списка ниже (или расширенного каталога по ADR).
- **timestamp** — обязательно.
- **task_id, actor, payload, trace_id** — опционально.

События **immutable**: после записи не изменяются и не удаляются (только append).

---

## Обязательные события по lifecycle Run

Следующие события должны быть записаны при соответствующих переходах, чтобы audit trail и оркестрация были согласованы:

| event_type | Когда | Кто записывает | Минимальный payload (рекомендация) |
|------------|--------|----------------|-------------------------------------|
| run_created | Run создан (status=created) | Molt | task_id, orchestrator |
| run_queued | Run поставлен в очередь | Molt | — |
| run_started | Run перешёл в running | Molt | executor (если есть) |
| run_waiting_approval | Run приостановлен, ожидает approval | Molt | approval_id, scope |
| run_resumed | Run продолжён после approval | Molt | approval_id |
| run_succeeded | Run завершён успешно | Molt | summary / artifact refs |
| run_failed | Run завершён с ошибкой | Molt | error_summary |
| run_cancelled | Run отменён | Molt | reason (опционально) |

Без этих событий Run lifecycle считается неполным для audit и отладки.

---

## События, связанные с Approval

| event_type | Когда | Примечание |
|------------|--------|------------|
| approval_requested | Создан Approval со status=requested | Runtime или Governance |
| approval_approved | Owner одобрил (status=approved) | Фиксируется при обновлении Approval |
| approval_rejected | Owner отклонил (status=rejected) | Фиксируется при обновлении Approval |

Запись approval_approved/approval_rejected может быть либо отдельным ExecutionEvent, либо дублированием в payload run_resumed / run_cancelled — на усмотрение реализации; контракт: факт approval должен быть восстановим из audit (Approval в shared-core + при необходимости события).

---

## Допустимые event_type (каталог)

Расширяемый список; минимальный набор для каноничности:

- `run_created`, `run_queued`, `run_started`, `run_waiting_approval`, `run_resumed`, `run_succeeded`, `run_failed`, `run_cancelled`
- `approval_requested`, `approval_approved`, `approval_rejected`
- `artifact_created` — при создании Artifact, привязанного к run_id
- `decision_created` — опционально, если Runtime логирует факт решения (обычно создаёт Governance)

Новые типы добавляются по необходимости с обновлением этого контракта и shared-schema (если нужна валидация enum).

---

## Связь с Run status

Переходы Run status должны сопровождаться соответствующим событием:

- created → run_created
- queued → run_queued
- running → run_started (и при необходимости шаговые события внутри run)
- waiting_approval → run_waiting_approval
- resumed → run_resumed
- succeeded / failed / cancelled → run_succeeded / run_failed / run_cancelled

Это обеспечивает прослеживаемость и возможность rollback/анализа по событиям.
