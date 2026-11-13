# Domain triage policy (Phase 10.0)

Правила, по которым triage определяет экспертизный домен по задаче и формирует explainability.

---

## Что делает triage (domain part)

1. **Анализирует** task text / owner request.
2. **Определяет** primary и при необходимости secondary expertise domains (из know_proff registry) через rule-based routing (keywords, typical_requests).
3. **Формирует** explainability: reason, matched_keywords.
4. **При необходимости** выбирает fallback (например universal domain или пустой primary с source=fallback).

---

## Что не делает triage

- Не принимает permission decisions.
- Не меняет task lifecycle (status, approval, run).
- Не заменяет approval policy.
- Не подменяет существующий routing domain (PRODUCT_DEV и т.д.) — тот остаётся в run_triage; expertise domain — дополнительный слой.

---

## Правила

1. **Сначала** rule-based routing (expert_routing.suggest_domains_for_task).
2. **Затем** attach metadata (primary, secondary, reason, matched_keywords).
3. **Затем** context selection (какие packs включить).
4. **Routing outcome всегда explainable** (reason, matched_keywords доступны owner).

---

## Fallback

- Если ни один домен не набрал порог — primary_domain может быть пустым или задан fallback-домен (например development/analytics); domain_selection_source = "fallback".
- Система не ломается при отсутствии уверенного совпадения.
