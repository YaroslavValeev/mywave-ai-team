# APPROVAL_CONTRACTS

Кто и когда создаёт approval, какие поля обязательны, как согласовать с shared-policy и shared-core.

Ссылка: [ADR-006](../decisions/ADR-006-approval-policy.md), [shared-policy config/approval.yaml](../../packages/shared-policy/config/approval.yaml), [ENTITY_CONTRACTS.md](ENTITY_CONTRACTS.md).

---

## Обязательные поля для Approval

| Поле | Обязательно | Источник |
|------|-------------|----------|
| approval_id | да | shared-core (при создании) |
| task_id | да | контекст задачи |
| scope | да | из списка approval_required_actions (shared-policy) |
| status | да | required \| requested \| approved \| rejected \| expired |
| requested_at | да | момент создания запроса |
| run_id | при привязке к Run | если approval блокирует конкретный Run |
| requested_by, approved_by, approved_at, comment | нет | по возможности заполнять |

**Scope** должен совпадать с одним из `scope` в `packages/shared-policy/config/approval.yaml` (approval_required_actions). Иначе контракт нарушен, интеграция и тесты должны это проверять.

---

## Кто создаёт Approval

1. **Governance (Agents):** при execute_gate после roundtable/court — когда по routing/policy для данного task_type требуется OWNER_APPROVAL_*. Создаёт запись со status=requested до передачи в Runtime.
2. **Runtime (Molt):** при выполнении шага, который по policy является approval-required (например, file write вне sandbox, git push, deploy). Создаёт Approval со status=requested, переводит Run в waiting_approval, останавливает продолжение.

Ни один слой не создаёт Approval «просто так»: только при срабатывании правила из shared-policy.

---

## Когда создаётся Approval

- **До** выполнения критического действия (ADR-006: «Approval request создаётся до критического действия»).
- Runtime **обязан** проверить по shared-policy, подпадает ли действие под approval_required_actions; если да — создать Approval, перевести Run в waiting_approval, не выполнять действие до approved.

---

## Кто обновляет Approval (approved / rejected)

Только **owner** (пользователь/владелец). По MVP канал для решения — Telegram (кнопки approve/reject). Обновление статуса в shared-core выполняет слой, обрабатывающий ответ owner (например, бот Agents или сервис, интегрированный с shared-core). Runtime только **читает** status и при approved продолжает Run (run_resumed → running), при rejected — run_failed или run_cancelled по правилам.

---

## Согласование scope с shared-policy

Список scope в approval.yaml:

- file_write_outside_sandbox
- code_changes
- patch_apply
- git_commit_push
- deploy_release
- external_api_actions
- telegram_send_production
- operations_with_pii
- money_legal_public
- destructive_ops

Любой новый scope добавляется в shared-policy (approval.yaml) и при необходимости в ADR-006; код и тесты проверяют, что создаваемые Approval используют только эти scope.

---

## Read-only

Read-only действия approve не требуют. Если действие не входит в approval_required_actions и не является записью/изменением/деструктивным — создавать Approval не нужно.

---

## Контракт для тестов

- В тестах: загрузка approval.yaml; проверка, что все scope из approval_required_actions присутствуют в каталоге допустимых scope (например, в shared-schema или константах); проверка, что при создании Approval с неизвестным scope валидация выдаёт ошибку или предупреждение.
