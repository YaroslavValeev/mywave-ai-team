# Domain context selection policy (Phase 10.0)

Как выбирается context pack для задачи и как формируется compact context.

---

## Как выбирается context pack

1. **Primary domain pack** — всегда включается, если primary_domain задан.
2. **Optional secondary packs** — до 1–2 дополнительных доменов по score (не более max_secondary, например 2).
3. **Max number of packs** — не более 3 (primary + 2 secondary), чтобы не раздувать контекст.
4. **Fallback:** если primary не задан или confidence низкий — можно включить один generic/fallback pack или не включать доменный контекст.
5. **When no domain is strong enough** — selected_context_packs может быть пустым или содержать один fallback; compact context тогда минимален.

---

## Правила

- Не тащить слишком много контекста (ограничение по числу пакетов и по размеру).
- Ограничивать шум: предпочитать primary + top secondary.
- Сохранять explainability: знать, какие ключи выбраны и почему.

---

## Compact context vs full domain profile

- **Selected context** = объединение выбранных context packs в ограниченном объёме: summary, strengths, typical_tasks (кратко), без полного текста know_proff.
- **Full domain profile** — только для детального просмотра (например /domain &lt;key&gt;); в triage и промптах используется compact.

- **Формирование compact:** из каждого выбранного pack берутся summary, до 5–7 strengths/keywords, до 3–5 typical_tasks; объём на pack ограничен (например 500–800 символов).
