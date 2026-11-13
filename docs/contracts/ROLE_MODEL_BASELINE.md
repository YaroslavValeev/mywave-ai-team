# Role model baseline (Phase 9.7)

Минимальный набор ролей для role-scoped views. Не full RBAC — практичный baseline.

---

## owner

- **Purpose:** Владелец продукта/системы; принимает решения, приоритизирует, видит полную картину.
- **What they need to see:** Глобальный dashboard, project drill-down, portfolio, strategic digests, next actions, decision queue, focus list, approvals, blockers, health.
- **What they should not be overloaded with:** Нет (owner — максимальный обзор по дизайну).
- **Minimal command/view scope:** /owner, /owner/portfolio, /owner/projects, /owner/project/{key}, все существующие owner-команды; /view_owner как компактный summary.

---

## operator

- **Purpose:** Отвечает за runtime, доступность Molt, операционную стабильность.
- **What they need to see:** Runtime health/ready, transport mode, degraded state, stuck items, backlog по задачам (что тормозит), метрики/состояние boundary при наличии.
- **What they should not be overloaded with:** Strategic digests, portfolio focus list, полный owner dashboard — достаточно runtime + stuck + degraded.
- **Minimal command/view scope:** /views/operator (web), /view_operator (Telegram): runtime summary, degraded cue, blockers/stuck, активные задачи count.

---

## executor

- **Purpose:** Исполняет задачи (например Cursor/runner); нужны assigned/active work, блоки, артефакты.
- **What they need to see:** Active tasks, recent artifacts, blocked/stuck items, next execution-relevant work (что в работе, что готово, что ждёт).
- **What they should not be overloaded with:** Portfolio, strategic digests, approval queue (если executor не принимает решения) — достаточно work items и блокеров.
- **Minimal command/view scope:** /views/executor (web), /view_executor (Telegram): active tasks, recent artifacts, blockers.

---

## reviewer

- **Purpose:** Принимает решения по задачам (approve/rework/clarify); нужна очередь на ревью.
- **What they need to see:** Pending approvals, decision queue, недавно разрешённые решения (recently resolved).
- **What they should not be overloaded with:** Runtime health, portfolio hotspots, full project drill-down — достаточно queue и решений.
- **Minimal command/view scope:** /views/reviewer (web), /view_reviewer (Telegram): pending approvals, decision queue.

---

## Итог

Четыре роли; у каждой — свой срез данных и свой компактный view/command. Owner сохраняет полный доступ; остальные роли получают укороченный, релевантный срез без шума.
