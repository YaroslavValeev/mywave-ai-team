# Portfolio heuristics (Phase 9.6)

Простые и объяснимые правила для portfolio layer. Без opaque scoring: любой сигнал owner может интерпретировать.

---

## Top problem project

Проект считается «problem» и выше в ранге, если:
1. **status == critical** — порог блокеров/rework/degraded превышен (pending >= 2, или degraded и active > 0, или rework_signals >= 2, или long_running >= 2).
2. **status == attention_needed** — есть хотя бы один из: pending >= 1, rework_signals >= 1, long_running >= 1.

**Ranking:** Сначала все critical (в любом порядке или по убыванию pending), затем attention_needed (по убыванию pending_count, затем rework_signals, затем long_running). Healthy проекты в конец или не включаются в «top problem» (зависит от limit).

**Explainability:** Каждый проект имеет reason из project health (например «Порог блокеров/rework/degraded превышен», «Есть pending / rework / long-running»).

---

## Approvals backlog hotspot

- **Условие:** pending_count по проекту > 0 (или >= 1).
- **Threshold для «backlog»:** уже 1 pending — попадание в список; при необходимости порог можно поднять до 2.
- **Ranking:** По убыванию pending_count.
- **Explainability:** «В проекте X — N pending approvals».

---

## Rework hotspot

- **Условие:** rework_signals по проекту > 0 (или >= 1; при желании порог 2 для «hotspot»).
- **Ranking:** По убыванию rework_signals.
- **Explainability:** «В проекте X — N сигналов rework (repeated rework или статус REWORK)».

---

## Degraded hotspot

- **Условие:** Система в состоянии DEGRADED (get_system_status_summary().state == "DEGRADED") и у проекта active_count > 0.
- **Смысл:** Проекты, у которых есть активная работа в момент недоступности runtime — они «затронуты» degraded.
- **Ranking:** По убыванию active_count.
- **Explainability:** «Система degraded; в проекте X — N активных задач (выполнение под риском)».

---

## Focus list

- **Источник:** Top N записей из top_problem_projects (например N = 5).
- **Suggested action:** Универсально «Разобрать блокеры / approvals / rework по проекту» или по status: critical → «Срочно разобрать»; attention_needed → «Выделить время на проект».
- **Explainability:** Каждый элемент focus list содержит project_key, status, reason (из project health) и suggested_action.

---

## Окна (freshness)

- **Portfolio overview / problem projects / hotspots / focus list:** Текущий снимок при запросе (без кэша по умолчанию).
- **Portfolio digest:** window_days = 7 (weekly) или 30 (monthly); содержимое может быть текущим snapshot по портфелю как proxy за период (без отдельного хранилища временных рядов в baseline).
