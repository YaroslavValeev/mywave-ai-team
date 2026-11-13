# docs/contracts

Контракты между слоями системы (Product, Governance, Runtime) и shared-пакетами.

## Документы

- **[ENTITY_CONTRACTS.md](ENTITY_CONTRACTS.md)** — канонические поля сущностей, обязательные поля, допустимые статусы.
- **[API_CONTRACTS.md](API_CONTRACTS.md)** — кто что вызывает в shared-core (Product, Governance, Runtime).
- **[EVENT_CONTRACTS.md](EVENT_CONTRACTS.md)** — обязательные события execution lifecycle (Run, Approval).
- **[APPROVAL_CONTRACTS.md](APPROVAL_CONTRACTS.md)** — кто создаёт/обновляет Approval, согласование с shared-policy.

## Сводка

- **Product ↔ shared-core:** создание Task/Project, чтение MemoryEntry/Artifact (см. API_CONTRACTS).
- **Governance ↔ shared-core:** чтение/обновление Task, создание Decision, запрос Approval; чтение shared-policy.
- **Molt ↔ shared-core:** создание Run, запись ExecutionEvent/Artifact, проверка Approval; чтение shared-policy.
