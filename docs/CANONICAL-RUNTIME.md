# AI Office System — канонический runtime и границы MVP control-plane

Документ фиксирует **единую операционную модель** репозитория: что считается истиной для production, что — fallback, какие модули входят в MVP, и какие проверки закрывают этап.

**Статус:** операционная канонизация (не спецификация новых фич).

---

## 1. Канонический runtime

### 1.1 Основной production-профиль (продуктовая истина)

**Основной профиль для AI Office System (роли, распределение по pipeline, LLM где доступен):**

| Имя профиля | `office-full` |
|-------------|---------------|
| Зависимости | `requirements.txt` (включает `crewai`) |
| Движок | `ORCHESTRATION_ENGINE=auto` (или `crewai`) |
| Секреты LLM | `OPENAI_API_KEY` и/или `OPENAI_BASE_URL` + `CREWAI_MODEL` / `CREWAI_DEFAULT_MODEL` |
| Смысл | Полный control-plane + **попытка** вызова CrewAI и ролей `STEP_PROFILES` (`app/orchestrator/crewai_bridge.py`); при сбое LLM — fallback на rule-based, если `ORCHESTRATION_ALLOW_FALLBACK=true`. |

### 1.2 Второй профиль (лёгкий / fallback)

| Имя профиля | `office-lite` |
|-------------|---------------|
| Зависимости | `requirements-minimal.txt` |
| Движок | **`ORCHESTRATION_ENGINE=rule_based`** (явно в `.env` для этого образа) |
| Смысл | Тот же конвейер **triage → pipeline → roundtable → court** без пакета CrewAI: только детерминированная логика и шаблонные handoffs. |

### 1.3 Иерархия

- **Основной (канон продуктовой модели «Office»):** `office-full`.
- **Fallback (ограниченный интеллект, тот же каркас управления):** `office-lite`.
- **`Dockerfile`** поддерживает два build target: **`lite`** (по умолчанию) и **`full`**.

Первый зафиксированный живой прогон: **[CANONICAL-SCENARIO-V1.md](CANONICAL-SCENARIO-V1.md)**.

### 1.3.1 Docker: какая команда → какой профиль

| Команда | Build target | Зависимости | Рекомендуемый `ORCHESTRATION_ENGINE` |
|---------|--------------|-------------|--------------------------------------|
| `docker compose up -d --build` | `lite` (default) | `requirements-minimal.txt` | `rule_based` |
| `DOCKER_BUILD_TARGET=full docker compose up -d --build` | `full` | `requirements.txt` (+ crewai) | `auto` |
| `docker build --target lite -t mywave:lite .` | `lite` | minimal | `rule_based` |
| `docker build --target full -t mywave:full .` | `full` | full | `auto` |

Для **office-full** в `.env` на сервере дополнительно: `OPENAI_API_KEY`, `ORCHESTRATION_ENGINE=auto`.

### 1.4 Где зафиксировано

| Место | Содержание |
|-------|------------|
| **Этот файл** | Канон имён профилей и иерархии |
| `README.md` | Краткая отсылка сюда |
| `Dockerfile` | Комментарий: какой профиль собирает данный файл |
| `.env.example` | Подсказки по `ORCHESTRATION_ENGINE` и LLM |

---

## 2. Сквозной сценарий (подтверждение)

**Цепочка целевого сценария:**

`Telegram → задача → orchestration → WAIT_OWNER → approve → execution → результат (артефакты)`

| Вопрос | Ответ |
|--------|--------|
| Пройден ли **живой** прогон Telegram → оркестрация → результат? | **Да, зафиксирован:** [CANONICAL-SCENARIO-V1.md](CANONICAL-SCENARIO-V1.md) раздел 4 — **task_id 8**, **2026-04-12**, профиль **office-lite**, контуру пройдены triage → pipeline → roundtable → court, гейт **WAIT_OWNER** с кнопками в Telegram; артефакты: `app/artifacts/tasks/task_8/`. |
| Что подтверждено **автоматически** в CI? | API-поток: `tests/test_e2e_api_flow.py`, `test_gate_wait_owner.py`, паритет approve `test_channel_parity.py`. |
| Нажатие Approve после скрина | Фиксируется оператором в «Дополнение после Approve» в том же документе при необходимости. |

**Ранее:** оценка времени до ручного E2E — закрыта фактическим прогоном v1 (см. документ сценария).

---

## 3. Границы MVP control-plane

### 3.1 Входит в MVP (модули)

- `app/main.py` — вход: бот + dashboard-процесс
- `app/bot/` — Telegram intake
- `app/dashboard/app.py`, `app/dashboard/api_router.py` — HTTP API и UI
- `app/orchestrator/sync_run.py` — **единый** синхронный цикл оркестрации
- `app/orchestrator/triage.py`, `pipeline.py`, `roundtable.py`, `court.py`
- `app/orchestrator/runtime.py` — фон/отмена (где используется)
- `app/orchestrator/crewai_bridge.py` — LLM-роли при профиле `office-full`
- `app/storage/` — модели, репозитории, миграции
- `app/shared/auth.py`, `audit.py`, `critical_flags.py`, `system_health.py`
- `app/governance/owner_flow.py` — связка WAIT_OWNER / approval
- `app/config/` — routing, policy, gateway yaml
- `app/mcp_server/` — опционально для операторов Cursor
- `app/gateway/` — секреты и capabilities

### 3.2 Ядро / вторичное / отключаемое

| Ядро | Вторичное | Временно отключаемое без потери смысла MVP |
|------|-----------|------------------------------------------|
| sync_run + storage + API + auth | Telegram (если есть только API) | MCP, gateway UI, office/game слой dashboard |
| triage → pipeline → roundtable → court | CrewAI (`office-full` only) | Локальный `app/runners/` (не в контейнере `app`) |

### 3.3 Не входит в текущий этап (чтобы не распыляться)

- Автоматический merge в `main` из runner
- Полная интеграция Google Cloud как исполнитель
- Обязательные отдельные микросервисы на каждую «роль»
- Замена БД единым «project memory» без миграций
- Публичный SaaS-multi-tenant

---

## 4. Формальный критерий «MVP control-plane завершён»

Этап считается **закрытым**, если одновременно:

1. **Зафиксирован канон** (раздел 1 этого документа) и команда согласна с профилями `office-full` / `office-lite`.
2. **Пройдены проверки:** `pytest` зелёный на целевой ветке; `GET /api/system/health` OK на стенде с выбранным профилем.
3. **Один сквозной сценарий подтверждён письменно:**
   - либо **API-only:** create task → orchestration → WAIT_OWNER → approve → терминальное состояние + артефакты на диске;
   - либо **с Telegram:** то же + ссылка на task id и перечень шагов (лог/скрин).
4. **SoT зафиксирован:** состояние задачи в БД — первично; файлы — производные (`ARTIFACTS_DIR`).

---

## 5. Риски и ограничения

1. **Самое слабое место:** неоднозначность профиля (образ на minimal + дефолт `auto` в коде приложения) без явного `ORCHESTRATION_ENGINE=rule_based` в env для lite-образа.
2. **При нагрузке:** монолитный `api_router.py`, долгие LLM-вызовы в запросе, отсутствие очереди задач.
3. **Рассинхрон:** **БД ↔ файлы артефактов** (рестарт, ручное удаление файлов); вторично — in-memory runtime vs персистентный `Run`.

---

## 6. Один следующий шаг (1 день)

**Привести репозиторий к одной несущей истине:** в `docker-compose` / `.env.example` для образа из текущего `Dockerfile` **явно задать** `ORCHESTRATION_ENGINE=rule_based` **или** перевести Dockerfile на `requirements.txt` для целевого `office-full` — **одно из двух**, задокументировано в README и коммите.

---

## 7. Роли Synthesizer, Devil’s Advocate, Adapter

В текущей архитектуре **правильнее всего**:

| Роль | Встраивание | Опора в коде |
|------|-------------|--------------|
| **Synthesizer** | **Этап** после сбора handoffs / в **court** — финальная сборка вердикта и отчёта | `app/orchestrator/court.py` |
| **Devil’s Advocate** | **Этапы pipeline / roundtable** — уже близко к `RC`, `RC2`, таблица рисков | `crewai_bridge.STEP_PROFILES`, `roundtable.py` |
| **Adapter** | **Policy + triage + routing** — приведение задачи к домену/контракту; при необходимости лёгкая **пост-обработка** перед записью handoff | `triage.py`, `app/config/routing.yaml`, `policy.yaml` |

**Не только пост-обработка:** критика и «адвокат дьявола» теряют силу, если не участвуют **до** финального вердикта; **synth** обязан быть **перед выдачей результата** owner-у.

---

## История изменений

| Дата | Изменение |
|------|-----------|
| 2026-04-10 | Первичная фиксация канона MVP control-plane |
