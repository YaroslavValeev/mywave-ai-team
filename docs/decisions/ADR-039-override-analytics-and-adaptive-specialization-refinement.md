# ADR-039: Override analytics and adaptive specialization refinement

## Статус

Принято (Phase 10.5).

## Контекст

После Phase 10.4 система уже выбирает effective domain context и agent specialization; owner может делать override. Сигналы override/fallback/mismatch логируются в audit, но не превращены в системную аналитику и refinement loop: нет агрегированной картины, где domain routing и specialization нуждаются в улучшении, где owner чаще вмешивается, какие execution lanes требуют расширения.

## Решение

Вводится **analytics layer** (только чтение, explainable):

- **Domain override analytics** — агрегация событий `domain_override` / `domain_override_cleared` по окну: summary, rate, by domain, by project, reason patterns, hotspots.
- **Specialization analytics** — агрегация `specialization_selected` / `specialization_fallback_used`: fallback summary, rate, by domain, by step, hotspots, weak execution lane summary, mismatch summary.
- **Refinement signals** — эвристики по данным аналитики: override-heavy domain/project, frequent fallback на domain+step, repeated mismatch; рекомендуемые действия (add/expand profile, review keywords, inspect override reasons).
- **Refinement backlog** — список actionable items для owner/GM: что улучшить вручную (реестр, routing, alias map), без автозаписи в registry.

Источники данных: существующий audit_events и текущие task/project/domain mappings. Отдельное хранилище не вводится.

## Принципы

- **Explainable** — каждое число и hotspot имеют понятный источник (event types, window, aggregation).
- **Evidence-based** — только факты из audit и задач.
- **Additive** — слой поверх существующего workflow и audit; не подменяет execution logic.
- **No opaque adaptive engine** — нет самообучающейся модели и black-box score.
- **No self-mutating registry** — реестр и policy меняются только вручную; analytics лишь подсказывает, где.

## Границы

- Analytics = read-only отчётность и рекомендации.
- Refinement = предложения owner/GM; выполнение изменений — вне scope этого слоя (ручной или отдельный workflow).
- Не смешивать analytics и execution logic в одном модуле.

## Non-goals

- Не делать self-learning system.
- Не делать auto-write в registry или policy.
- Не строить отдельную BI-платформу.
- Не вводить black-box quality score для доменов или специализаций.

## Следствия

- Нужен сервис аналитики (domain_specialization_analytics.py), presenters, web/Telegram entrypoints.
- Owner recommendations могут включать refinement signals (override-heavy domain, fallback hotspot, project needing refinement).
- Документация: модели аналитики, эвристики, refinement backlog, playbooks.
