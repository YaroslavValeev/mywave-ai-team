# shared-policy (draft)

Единый policy layer для routing, approval rules, critical actions, permissions и escalation.

## Назначение

- Убрать policy из prompt-only и распределённой логики.
- Сохранить единые правила между Telegram/API/MCP/Dashboard.
- Поддержать управляемую миграцию без разрыва совместимости.

## Состав (черновик)

- `approval_rules.yaml`
- `routing_contract.yaml`
- далее: policy test fixtures и compatibility checks.

## Основной принцип

Read-only не требует approve.  
Critical external actions требуют owner approval.
