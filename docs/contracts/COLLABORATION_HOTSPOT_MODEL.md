# Collaboration hotspot model (Phase 10.9)

## Поля

- **hotspot_type** — approval_bottleneck | review_execution_loop | runtime_escalation_gap | owner_attention_gap | domain_handoff_mismatch.
- **roles_involved** — [source_role, target_role] или список ролей.
- **project_key** — проект (если применимо).
- **domain_key** — домен (если применимо).
- **reason** — краткое объяснение.
- **severity** — high | medium | low.
- **evidence_summary** — счётчики, task_ids (кратко).
- **recommended_collaboration_action** — что сделать (например «Разобрать approvals», «Координировать owner–executor»).

## Примеры hotspot_type

- **approval_bottleneck** — много ожидающих решений owner; блокировка executor→owner.
- **review_execution_loop** — повторный rework; цикл owner↔executor.
- **runtime_escalation_gap** — DEGRADED или блокеры; operator должен эскалировать.
- **owner_attention_gap** — в проекте смешаны pending + long-running + rework; owner перегружен.
- **domain_handoff_mismatch** — override-heavy или unstable domain + pending; контекст handoff неясен.
