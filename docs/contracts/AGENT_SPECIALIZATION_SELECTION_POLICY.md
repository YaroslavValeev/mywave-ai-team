# Agent specialization selection policy (Phase 10.4)

## На что опирается выбор

- **Effective primary domain** — из get_effective_domain_context (с учётом override).
- **Workflow step** — pipeline, roundtable, court.
- **Override status** — не меняет логику выбора профиля; домен уже учтён в effective.
- **Task text / matched keywords** — опционально для refinement; на первом этапе достаточно domain + step.
- **Project-domain signals** — опционально для будущего уточнения.

## Как происходит выбор

1. **Baseline:** по паре (effective_primary_domain, workflow_step) ищем в реестре профиль с совпадающими domain_key и workflow_step.
2. **Refinement:** если найдено несколько — берём первый подходящий или по signal_keywords по тексту задачи (если реализовано).
3. **Fallback:** если совпадения нет — используем профиль с domain_key = "general" и данным workflow_step (general_pipeline, general_roundtable, general_court).
4. **Always explainable:** в ответе указываем selection_reason (matched domain+step / fallback), matched_signals (если есть), fallback_used (true/false).

## Требования

- Всегда объяснимый выбор.
- Без opaque ranking.
- Предсказуемый fallback.
- Компактный вывод (без сырого дампа реестра).
