# shared-core

Единый владелец сущностей (Source of Truth): Project, Task, Run, Decision, Approval, Artifact, MemoryEntry, ExecutionEvent. Владеет генерацией ID, репозиториями, контрактами storage и memory.

## Назначение

- **ID generation:** task_id, run_id, decision_id, approval_id, artifact_id, memory_id, event_id создаются только здесь (фабрики в `ids.py`).
- **Repositories:** интерфейсы TaskRepository, RunRepository, DecisionRepository, ApprovalRepository, MemoryRepository, ArtifactRepository, EventRepository — в `repositories.py` / `protocols.py`.
- **Registry:** регистрация и разрешение сущностей по id (опционально registry.py).
- **Memory:** контракт доступа к проектной памяти (memory.py).
- **Storage:** единый протокол хранения (storage.py); конкретная реализация (SQLite, PostgreSQL и т.д.) подключается через адаптеры.

Ни один слой (Product, Governance, Runtime) не создаёт task_id/run_id самостоятельно и не пишет напрямую в storage — только через shared-core.

## Ссылки

- [ADR-002: Source of Truth](../../docs/decisions/ADR-002-source-of-truth.md)
- [ENTITY_CONTRACTS](../../docs/contracts/ENTITY_CONTRACTS.md)
- [API_CONTRACTS](../../docs/contracts/API_CONTRACTS.md)
- [shared-schema](../shared-schema/) — типы сущностей (shared_core может зависеть от shared_schema или дублировать контракты до стабилизации).

## Структура

- `ids.py` — TaskIdFactory, RunIdFactory, и прочие фабрики ID.
- `protocols.py` — абстрактные интерфейсы (Protocol) для репозиториев и storage.
- `repositories.py` — интерфейсы репозиториев (Task, Run, Decision, Approval, Memory, Artifact, ExecutionEvent).
- `registry.py` — опциональный реестр сущностей по id.
- `memory.py` — контракт MemoryRepository / memory access.
- `storage.py` — единый Storage protocol (read/write по сущностям).
- `service_layer.py` — фасад: создание Task/Run/Decision/Approval с выдачей ID и делегированием в репозитории.
- `crosswalk.py` — маппинг legacy_id ↔ canonical_id (ADR-008).
- `storage_impl/` — реализации StorageProtocol: InMemoryStorage (тесты, smoke), SQLiteStorage (локальный store). См. ADR-007.
- `adapters/` — compatibility adapters (stubs): personal_helper_adapter, agents_adapter, molt_adapter. См. ADAPTER_STRATEGY.

## Использование

```python
from shared_core.storage_impl import InMemoryStorage, SQLiteStorage
from shared_core import service_layer

storage = InMemoryStorage()  # или SQLiteStorage("path/to.db")
task = service_layer.create_task(storage, {
    "project_id": project["project_id"], "title": "T", "description": "D",
    "priority": "high", "origin_channel": "telegram",
})
run = service_layer.create_run(storage, task["task_id"], "molt")
```

Подключение к legacy-коду — через adapters и crosswalk; массовый перенос только после стабилизации одного E2E flow.
