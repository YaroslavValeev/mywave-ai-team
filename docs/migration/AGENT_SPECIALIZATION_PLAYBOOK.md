# Agent Specialization Playbook (Phase 10.4)

## Как выбирается specialization

1. **Вход:** `task_id`, `workflow_step` (pipeline / roundtable / court), опционально `task_text`.
2. **Effective domain:** берётся из `get_effective_domain_context(task_id, task_text)` — с учётом override (Phase 10.1–10.2).
3. **Поиск в реестре:** ищется профиль с парой `(domain_key, workflow_step)` в `app/data/agent_specializations/specializations.yaml`.
4. **Fallback:** если пары нет — используется `general_pipeline`, `general_roundtable` или `general_court` соответственно.
5. **Результат:** объект execution lane: `selected_specialization`, `execution_focus`, `expected_output_type`, `guardrails`, `selection_reason`, `fallback_used`.

Выбор детерминированный и объяснимый; непрозрачного скоринга нет.

## Связь с domain и workflow step

- **Domain** задаёт предметный контекст (legal, programming_engineer, finance, general и т.д.).
- **Step** задаёт фазу: pipeline (выполнение/анализ), roundtable (обзор, trade-offs), court (итог, решение).
- **Specialization** — это профиль для пары (domain, step): как именно выполнять шаг (focus, style, expected output, guardrails).

Один и тот же домен даёт разные профили для pipeline, roundtable и court (например, legal_pipeline_analysis, legal_roundtable_review, legal_court_decision).

## Как owner/debug видят specialization

- **Карточка задачи (/task &lt;id&gt;):** строка «Профиль (pipeline): &lt;profile_name&gt;» и пометка «(fallback)», если использован general.
- **Telegram:** `/task_specialization <id>` — по шагам pipeline, roundtable, court: выбранный профиль, причина, fallback.
- **API:** `GET /api/tasks/{id}/specialization-context` — effective_domain, per_step (pipeline/roundtable/court), explainability, fallback_used_any.

Не перегружаем основной UI; детали — в debug/API и в команде `/task_specialization`.

## Как читать fallback

- **fallback_used = true** означает: для эффективного домена в реестре нет записи с данным шагом, поэтому взят общий профиль (general_pipeline / general_roundtable / general_court).
- Если fallback часто по одному домену — в рекомендациях может появиться сигнал **specialization_fallback_hotspot**: стоит проверить реестр и при необходимости добавить профиль для этого домена и шага.
- Fallback не ошибка: система остаётся работоспособной; профиль просто менее специфичен.

## Что такое execution_focus

- **execution_focus** — короткое описание того, на чём агент должен сконцентрироваться на этом шаге (например: «analysis of terms, obligations, risks» для legal pipeline; «trade-offs, alternatives» для roundtable).
- Попадает в prompt/context шага (см. AGENT_PROMPT_ENVELOPE_BASELINE) и ограничивает объём (~200–400 символов), чтобы не раздувать промпт.

## Когда система использует specialization по умолчанию

- При каждом запуске шага workflow (pipeline, roundtable, court) вызывается `build_execution_lane(task_id, step)`.
- Результат используется для: (1) блока «Execution profile» в handoff/report, (2) аудита (specialization_selected / specialization_fallback_used), (3) передачи в следующий шаг при необходимости.
- По умолчанию для неизвестного домена или шага всегда подставляется general_* для данного шага — без падений и opaque-логики.
