# shared-schema (draft)

Единый контракт доменных сущностей для Product/Governance/Runtime.

## Назначение

- Зафиксировать канонические сущности и поля.
- Дать единые типы/контракты для API, storage и runtime.
- Устранить расхождения между слоями.

## Состав (черновик)

- `entities.yaml` — канонический реестр сущностей и обязательных полей.
- `handoff_v1.yaml` — Structured I/O между L3 шагами pipeline (ADR-007).
- Далее: JSON Schema/OpenAPI fragments + versioning.

## Версионирование

- Semantic-ish schema version: `v0-draft`, `v1`, `v1.1`.
- Любое breaking изменение проходит через ADR + migration notes.
