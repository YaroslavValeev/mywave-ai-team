# Domain workflow integration points (Phase 10.1)

Где в workflow появляется domain-aware context и что при этом не меняется.

---

## 1. После run_triage (orchestration)

- **Вход:** task_id, task.owner_text.
- **Добавляется:** вызов get_effective_domain_context(task_id, task.owner_text); результат кладётся в triage_result["workflow_domain_context"]; логируется audit domain_triage (уже было) и при первом использовании — domain_context_used.
- **Не меняется:** run_triage, update_task (domain/task_type/criticality), canonical run/approval flow.
- **Безопасность:** при недоступности domain layer workflow идёт дальше без workflow_domain_context; fallback тихий.

---

## 2. Перед pipeline / roundtable / court

- **Вход:** triage_result (уже может содержать workflow_domain_context).
- **Добавляется:** pipeline/roundtable/court принимают triage_result как есть; при наличии workflow_domain_context могут читать compact_context и primary domain.
- **Не меняется:** сигнатуры run_pipeline, run_roundtable, run_court (дополнительный ключ в dict); логика шагов и approval не зависит от domain context.
- **Безопасность:** если ключа нет или compact_context пуст — поведение как раньше.

---

## 3. Сборка agent prompt/context envelope (pipeline handoff, court report)

- **Вход:** triage_result с workflow_domain_context.
- **Добавляется:** в первый handoff .md или в court report добавляется секция «Domain context (expertise)» с compact_context (или краткой выжимкой), чтобы downstream/executor мог использовать доменную экспертизу.
- **Не меняется:** структура handoff payload, решение court, генерация summary.
- **Безопасность:** ограничение длины compact_context (например 1000–1500 символов); не подставляется сырой know_proff.

---

## 4. Task detail / owner card

- **Вход:** task_id, task (owner_text).
- **Добавляется:** при построении карточки вызывается get_effective_domain_context; в ответ добавляются effective primary, domain_override, override_reason (если есть).
- **Не меняется:** остальные поля карточки, права доступа.
- **Безопасность:** только отображение; override не меняет статус/approval.

---

## 5. Owner override flow

- **Вход:** /set_task_domain &lt;id&gt; &lt;domain_key&gt; [reason]; валидация domain_key по registry.
- **Добавляется:** запись override в domain_override_store; audit domain_override; ответ owner-у.
- **Не меняется:** task status, approval, run; пересчёт effective context при следующем чтении/workflow run.
- **Безопасность:** только owner (или проверка is_owner); валидация domain_key.
