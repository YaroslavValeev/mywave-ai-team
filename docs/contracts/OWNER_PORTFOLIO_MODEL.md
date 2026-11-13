# Owner portfolio model (Phase 9.6)

Формализация блоков portfolio layer: purpose, source of truth, grouping/ranking, output shape, freshness.

---

## portfolio_overview

- **Purpose:** Общий снимок портфеля: количество проектов, разбивка по health, суммарные active/pending, состояние системы.
- **Source of truth:** project_queries.list_projects(), owner_queries.get_system_status_summary().
- **Grouping logic:** Агрегация по всем project groups из list_projects.
- **Ranking logic:** Не применимо (сводные счётчики).
- **Output shape:** projects_count, critical_count, attention_needed_count, healthy_count, total_active, total_pending, system_state (OK/DEGRADED), rework_total, long_running_total.
- **Freshness:** При каждой загрузке страницы / вызове команды.

---

## portfolio_health_summary

- **Purpose:** Краткая сводка здоровья портфеля для блока на dashboard.
- **Source of truth:** list_projects; агрегация status по проектам.
- **Output shape:** То же, что portfolio_overview, или подмножество полей для compact view.
- **Freshness:** При загрузке.

---

## top_problem_projects

- **Purpose:** Ранжированный список проектов, требующих наибольшего внимания.
- **Source of truth:** list_projects (уже отсортирован: critical → attention_needed → по pending/rework/long_running).
- **Grouping logic:** По project_key.
- **Ranking logic:** 1) status == critical; 2) status == attention_needed; 3) по убыванию pending_count, rework_signals, long_running. См. PORTFOLIO_HEURISTICS.
- **Output shape:** Список { project_key, project_label, status, reason, pending_count, rework_signals, long_running, active_count } с limit.
- **Freshness:** При загрузке.

---

## approvals_backlog_by_project

- **Purpose:** Где скапливаются pending approvals по проектам.
- **Source of truth:** list_projects (поле pending_count по проекту).
- **Grouping logic:** По project_key.
- **Ranking logic:** По убыванию pending_count; только проекты с pending_count > 0.
- **Output shape:** Список { project_key, project_label, pending_count }.
- **Freshness:** При загрузке.

---

## rework_hotspots

- **Purpose:** Проекты с повышенным повторным rework.
- **Source of truth:** list_projects (rework_signals по проекту).
- **Grouping logic:** По project_key.
- **Ranking logic:** По убыванию rework_signals; только rework_signals > 0 (или >= threshold из heuristics).
- **Output shape:** Список { project_key, project_label, rework_signals, reason }.
- **Freshness:** При загрузке.

---

## degraded_hotspots

- **Purpose:** При состоянии DEGRADED — какие проекты затронуты (имеют активную работу).
- **Source of truth:** list_projects + get_system_status_summary(); при state == DEGRADED — проекты с active_count > 0.
- **Grouping logic:** По project_key.
- **Ranking logic:** По убыванию active_count.
- **Output shape:** Список { project_key, project_label, active_count, reason } или пустой список, если система не degraded.
- **Freshness:** При загрузке.

---

## portfolio_focus_list

- **Purpose:** 3–5 проектов/зон для приоритетного внимания owner (actionable focus list).
- **Source of truth:** top_problem_projects (top N с объяснением).
- **Ranking logic:** Как у top_problem_projects; берём первые limit с кратким suggested_action/reason.
- **Output shape:** Список { project_key, project_label, status, reason, suggested_action }.
- **Freshness:** При загрузке.

---

## portfolio_digest

- **Purpose:** Weekly (или monthly) portfolio-level сводка: cross-project view за окно.
- **Source of truth:** portfolio_overview, top_problem_projects, portfolio_focus_list, approvals_backlog_by_project, rework_hotspots, degraded_hotspots (агрегаты за окно или текущий снимок).
- **Grouping logic:** По проектам; окно window_days (7 или 30).
- **Output shape:** window_days, overview snapshot, top_problem_projects (limit), focus_list, approvals_backlog_summary, rework_hotspots_count, degraded_hotspots_count или список.
- **Freshness:** При отправке weekly digest или по запросу; не обязательно real-time за окно (можно текущий snapshot как proxy).
