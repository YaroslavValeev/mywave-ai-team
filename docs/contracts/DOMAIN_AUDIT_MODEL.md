# Domain audit model (Phase 10.1)

События и поля для аудита domain selection и override.

---

## События (event_type)

- **domain_triage** — автоматический подбор домена по тексту (уже в Phase 10.0).
- **domain_override** — установка или смена owner override (task_id, new_primary_domain, reason, actor).
- **domain_context_used** — использование effective domain context в workflow (при первом проходе pipeline или при сборке контекста для задачи).

---

## Минимальные поля в payload

- **task_id**
- **primary_domain** (effective)
- **secondary_domains** (список)
- **source** (auto / override / fallback)
- **reason** (текст)
- **actor** (при override)
- **override** (bool)
- **selected_context_pack_keys**

Используется существующий audit pattern (AuditEvent, add_audit_event / log_audit).
