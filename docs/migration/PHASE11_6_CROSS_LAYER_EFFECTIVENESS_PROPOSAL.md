# Phase 11.6 — Cross-layer effectiveness synthesis (предложение)

> **Дубликат в корне монорепы (если воркспейс = `MyWaveAITeam`):**  
> `docs/migration/PHASE11_6_CROSS_LAYER_EFFECTIVENESS_PROPOSAL.md`

**Цель:** единый **explainable** слой, который связывает итоги эффективности из разных слоёв продукта (без смешения lifecycle сущностей Run/Task/Approval), чтобы owner/GM видели **согласованную картину**: что улучшилось после интервенций в collaboration, tuning, (опционально) refinement — и где конфликт сигналов.

**Не делаем в 11.6:** opaque scoring, авто-действия, перенос SoT из shared-core, LLM как источник истины.

---

## 1. Артефакты (документы и контракты)

| Артефакт | Назначение |
|----------|------------|
| `docs/decisions/ADR-050-cross-layer-effectiveness-synthesis.md` | Границы слоёв, non-goals, источники истины по слоям |
| `docs/contracts/CROSS_LAYER_EFFECTIVENESS_MODEL.md` | Сущность `EffectivenessSlice`, поля, owner слоя, окна |
| `docs/contracts/CROSS_LAYER_EFFECTIVENESS_SYNTHESIS.md` | Правила агрегации (детерминированные), приоритет конфликтов |
| `docs/contracts/CROSS_LAYER_EFFECTIVENESS_AUDIT.md` | События `cross_layer_effectiveness_*` |
| `docs/migration/PHASE11_6_ACCEPTANCE.md` | DoD и ручная проверка |
| `docs/migration/CROSS_LAYER_EFFECTIVENESS_PLAYBOOK.md` | Как читать synthesis owner/GM |

**Связь с существующим:** только **чтение** уже сохранённых tuning outcomes и collaboration outcomes + опционально refinement signals (counts), без дублирования их store.

---

## 2. Сервисы (код)

| Модуль | Ответственность |
|--------|-----------------|
| `app/services/cross_layer_effectiveness_store.py` | Опционально: кеш последнего synthesis snapshot (JSON), env `CROSS_LAYER_EFFECTIVENESS_PATH` — **или** только on-demand без persist v1 |
| `app/services/cross_layer_effectiveness.py` | `build_effectiveness_slices(window_days)`, `synthesize_cross_layer_summary(window_days)`, `get_layer_alignment_signals()` — конфликт: collaboration improved + tuning worse |
| `app/services/cross_layer_effectiveness.py` | `list_projects_effectiveness_cross_cut(project_key, window_days)` — проектный срез при наличии project-scoped inputs |

**Входы (read-only):**
- `tuning_outcomes` / `get_tuning_outcome_summary`, `list_tuning_outcomes`
- `collaboration_outcomes` / `get_collaboration_effectiveness_summary`, `list_collaboration_outcomes`
- Опционально Phase 10.x: `get_refinement_signals` или счётчики из refinement backlog (без merge в одну «оценку»)

**Выход:** структура `CrossLayerEffectivenessSummary` + список `alignment_items[]` (текст + evidence refs: `tuning_candidate_id`, `execution_id`, `outcome_id`).

---

## 3. Surfaces (UI / API / Telegram)

| Surface | Минимум |
|---------|---------|
| Web | `/owner/effectiveness` или блок на `/owner` «Cross-layer effectiveness» со ссылкой |
| Web | Компактная полоса на `/owner/portfolio` и `/owner/tuning/outcomes` — «см. synthesis» |
| API | `GET /api/owner/effectiveness/synthesis?window_days=30` |
| Telegram | `/effectiveness_synthesis [дней]` — короткий текст + top 3 alignment |

**Presenters:** `app/presenters/cross_layer_effectiveness_presenters.py` — карточка, список, Telegram formatter.

---

## 4. Тесты

| Тест | Проверка |
|------|----------|
| `test_cross_layer_slice_shape` | Форма slice по каждому слою |
| `test_synthesis_is_explainable` | Нет числового black-box; есть evidence refs |
| `test_alignment_conflict_detected` | При моках: collaboration effective + tuning worse → alignment item |
| `test_synthesis_api_and_routes_wired` | 200 на API, страница рендерится |
| `test_telegram_effectiveness_synthesis_command` | Handler зарегистрирован |
| `test_recommendations_include_cross_layer_signal` | Один top-level сигнал при конфликте/сильном рассогласовании (порог в коде) |
| `test_existing_collaboration_and_tuning_outcomes_untouched` | Регрессия store/lifecycle |

---

## 5. Порядок реализации (миграция)

1. ADR-050 + контракты + playbook + acceptance outline  
2. `cross_layer_effectiveness.py` (on-demand only) + presenters  
3. API + одна страница owner  
4. Telegram  
5. Одна рекомендация в `owner_recommendations` (строгий порог)  
6. Опционально persist snapshot store  
7. Тесты и `PHASE11_6_ACCEPTANCE.md`

**Rollback:** отключить роуты и handler; сервис не пишет в task/run store.

---

## 6. Критерий готовности 11.6

- Synthesis читает ≥2 слоя (минимум tuning + collaboration).  
- Каждый вывод трассируем к id записей исходных outcomes.  
- Owner видит одну страницу/команду без дублирования метрик без контекста.  
- Тесты зелёные; ADR и acceptance зафиксированы.
