# Domain override lifecycle (Phase 10.2)

## Состояния

- **Auto-selection** — по тексту задачи выбран primary_domain и context; override отсутствует.
- **Override set** — владелец установил new_primary_domain через `/set_task_domain` или web; запись в store с override_active=true.
- **Override active** — при чтении effective context используется override; compact_context строится для new_primary_domain.
- **Override cleared** — вызов clear_override (или `/clear_task_domain`); в store override_active=false; при следующем чтении effective context = auto-selection по тексту задачи.

## События audit

- **domain_triage** — авто-подбор при triage.
- **domain_override** — установка override (set).
- **domain_override_cleared** — снятие override (clear).
- **domain_context_used** — использование контекста в workflow.

## Effective context после clear

После clear_override(task_id) get_effective_domain_context(task_id, task_text) возвращает результат auto-selection по task_text (как если бы override не было). Override запись в store остаётся для истории, но override_active=false и она не используется.
