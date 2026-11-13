# Owner command model (Phase 9.2)

Минимальный набор owner-команд для Telegram-first режима. Префикс `/`; доступ только для owner (owner_chat_id из конфига).

---

## /help

**Назначение:** Показать список доступных команд и краткое описание.

**Входные параметры:** Нет.

**Expected output:** Текст со списком команд: /status, /tasks, /task, /approvals, /artifacts, /runs, /health, /summary, /digest, /blockers, /decisions, /done, /insights, /next, /decisions_queue, /health_projects, /risks, /weekly_digest, /monthly_digest, /projects, /project &lt;key&gt;, #TASK для создания задачи.

**Source of truth:** Документация (этот файл, OWNER_OPERATIONS_PLAYBOOK).

**Ограничения:** Только owner.

---

## /status

**Назначение:** Краткая operational сводка: transport mode, Molt health/ready, active tasks, pending approvals, recent artifacts, system state (OK / DEGRADED / …).

**Входные параметры:** Нет.

**Expected output:** Человекочитаемое сообщение: режим, Molt up/down, счётчики, состояние.

**Source of truth:** owner_queries.get_system_status_summary(), опционально GET MOLT_HTTP_BASE_URL/health.

**Ограничения:** Только owner. При недоступности Molt в HTTP mode — явно показать DEGRADED / HTTP runtime down.

---

## /tasks

**Назначение:** Показать последние или активные задачи (список).

**Входные параметры:** Опционально limit (по умолчанию 10).

**Expected output:** Список задач: id, status, кратко owner_text или дата.

**Source of truth:** TaskRepository.get_all_tasks() / owner_queries.get_active_tasks(limit).

**Ограничения:** Только owner.

---

## /task &lt;id&gt;

**Назначение:** Карточка задачи: task_id, status, current run, approval state, последний артефакт/событие.

**Входные параметры:** id — номер задачи (legacy task_id).

**Expected output:** Форматированная карточка: id, status, run_id (если есть), approval (если ждёт), report_path/summary (если есть).

**Source of truth:** TaskRepository.get_task(), get_canonical_state(task_id).

**Ограничения:** Только owner. При несуществующем id — сообщение «Задача не найдена».

---

## /approvals

**Назначение:** Показать задачи, ожидающие решения owner (pending approvals).

**Входные параметры:** Опционально limit (по умолчанию 10).

**Expected output:** Список задач в статусе WAIT_OWNER (и при необходимости APPROVED_WAIT_MERGE) с id и кратким контекстом.

**Source of truth:** owner_queries.get_pending_approvals(limit) — задачи со status in (WAIT_OWNER, APPROVED_WAIT_MERGE).

**Ограничения:** Только owner.

---

## /artifacts

**Назначение:** Показать последние артефакты (результаты, отчёты).

**Входные параметры:** Опционально limit (по умолчанию 10).

**Expected output:** Список: задача id, report_path/summary, дата.

**Source of truth:** owner_queries.get_recent_artifacts(limit) — задачи с report_path или summary, упорядоченные по дате.

**Ограничения:** Только owner.

---

## /runs

**Назначение:** Краткая сводка по «запускам» (задачи с активным run — не DONE/ARCHIVED и с run_id в canonical state).

**Входные параметры:** Опционально limit.

**Expected output:** Список задач в работе: id, status, run_id (если есть).

**Source of truth:** owner_queries.get_runs_summary(limit).

**Ограничения:** Только owner.

---

## /health

**Назначение:** Быстрая проверка: Molt доступен? (при MOLT_TRANSPORT_MODE=http — GET /health). Иначе — режим local/stub и текст «Molt in-process».

**Входные параметры:** Нет.

**Expected output:** Molt: up / down / n/a (local).

**Source of truth:** GET MOLT_HTTP_BASE_URL/health при mode=http.

**Ограничения:** Только owner.

---

## /summary

**Назначение:** Развёрнутая owner-facing сводка: top N active tasks, последние approvals, последние artifacts, статус Molt, признаки degraded.

**Входные параметры:** Нет (внутри можно ограничить N).

**Expected output:** Человекочитаемое многострочное сообщение.

**Source of truth:** owner_summary.build_detailed_summary(), owner_queries.

**Ограничения:** Только owner.

---

## /digest

**Назначение:** Недельная управленческая сводка (weekly digest).

**Source of truth:** owner_insights.get_weekly_digest().

---

## /blockers

**Назначение:** Показать что тормозит: degraded, waiting decisions, long-running.

**Source of truth:** owner_insights.get_blockers_summary().

---

## /decisions

**Назначение:** Показать задачи, которые ждут решения owner.

**Source of truth:** owner_insights.get_awaiting_decisions_summary().

---

## /done

**Назначение:** Показать завершённое за последнее окно и доступные артефакты.

**Source of truth:** owner_insights.get_completed_recently_summary().

---

## /insights

**Назначение:** Компактная management-картина: project activity, rework signals, degraded signals, long-running.

**Source of truth:** owner_insights.* summary functions.

---

## Phase 9.3 — Strategic recommendation commands

### /next

**Назначение:** Топ 3–5 следующих действий для owner: approvals pending, blockers, repeated rework, degraded, stalled.

**Входные параметры:** Нет (внутри limit=5).

**Expected output:** Приоритизированный список: что сделать, почему, важность.

**Source of truth:** owner_recommendations.get_next_actions(limit), owner_recommendation_presenters.format_next_actions.

**Ограничения:** Только owner.

---

### /decisions_queue

**Назначение:** Приоритизированная очередь решений: pending approvals, rework requiring owner, long-running/stuck, degraded-related.

**Expected output:** Список: item, reason, priority, suggested next action.

**Source of truth:** owner_recommendations.get_decision_queue(limit), format_decision_queue.

---

### /health_projects

**Назначение:** Project health baseline по группам: healthy / attention_needed / critical.

**Expected output:** Группы проектов с статусом и кратким обоснованием.

**Source of truth:** owner_recommendations.get_project_health_summary(), format_project_health_summary.

---

### /risks

**Назначение:** Risk signals с объяснением: почему важно, что делать.

**Expected output:** Список рисков с reason и suggested action.

**Source of truth:** owner_recommendations.get_risk_signals(), format_risk_signals.

---

### /weekly_digest

**Назначение:** Стратегическая недельная сводка: key risks, what moved, what stalled, what needs decision, what to prioritise next week.

**Expected output:** Strategic weekly digest (то же содержимое, что у scheduled weekly notification).

**Source of truth:** owner_recommendations.get_strategic_weekly_digest(), format_strategic_weekly_digest.

---

### /monthly_digest

**Назначение:** Baseline месячная сводка (last 30 days): completed, active, pending approvals, rework/degraded counts, top blockers, top recommendations.

**Expected output:** Monthly digest text.

**Source of truth:** owner_recommendations.get_monthly_digest_baseline(), format_monthly_digest_baseline.

---

## Phase 9.5 — Project layer commands

### /projects

**Назначение:** Список проектов (project groups) с health и счётчиками active/pending.

**Expected output:** Текст со списком: project_label, status, active_count, pending_count; подсказка про /project <key> и dashboard.

**Source of truth:** project_queries.list_projects(), project_presenters.format_project_list_text.

---

### /project &lt;key&gt;

**Назначение:** Карточка проекта: overview, health, active/pending/artifacts, кол-во risks и decision queue, ссылка на dashboard.

**Входные параметры:** key — project_key (например general или domain/task_type).

**Expected output:** Краткая карточка + ссылка на /owner/project/{key}.

**Source of truth:** project_queries.get_project_overview, get_project_health, get_project_risks, get_project_decision_queue; format_project_card_text.

---

## Phase 9.6 — Portfolio layer commands

### /portfolio

**Назначение:** Краткий overview по портфелю (cross-project): projects count, health breakdown, total active/pending, rework/long-running, system state.

**Source of truth:** owner_portfolio.get_portfolio_overview(), format_portfolio_overview_text.

---

### /focus

**Назначение:** 3–5 top focus items across projects (actionable list с suggested_action).

**Source of truth:** owner_portfolio.get_portfolio_focus_list(), format_focus_list_text.

---

### /hotspots

**Назначение:** Rework hotspots и degraded hotspots (при degraded — затронутые проекты).

**Source of truth:** owner_portfolio.get_rework_hotspots(), get_degraded_hotspots(); format_hotspots_text.

---

### /approvals_backlog

**Назначение:** Approvals backlog по проектам (pending count по каждому проекту).

**Source of truth:** owner_portfolio.get_approvals_backlog_by_project(), format_approvals_backlog_text.

---

## Канонический формат

Команды с префиксом `/` обрабатываются aiogram Command filter. Если в проекте уже используется иной префикс или формат для части команд — не ломать существующий контур; каноническая модель для новых owner-команд — `/` как выше.
