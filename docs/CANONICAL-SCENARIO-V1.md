# CANONICAL SCENARIO v1 — первый живой прогон AI Office (Telegram → результат)

**Цель:** один раз зафиксировать, что система проходит **единый цикл**: intake → orchestration → (при необходимости) approve → ответ в Telegram → артефакты на диске.

**Статус отчёта:** раздел 4 заполнен по **живому прогону 2026-04-12** (Telegram, task_id **8**, скрин подтверждения цепочки до гейта `WAIT_OWNER`).

---

## 1. Зафиксированный профиль для v1


| Параметр | Значение |
|----------|----------|
| **Профиль** | `office-lite` |
| **Обоснование** | Образ из корневого `Dockerfile` = `requirements-minimal.txt` (без CrewAI). В `docker-compose.yml` по умолчанию `ORCHESTRATION_ENGINE=rule_based`. Тот же конвейер `sync_run.py`: triage → pipeline → roundtable → court. |
| **Продуктовый канон** | Полный AI Office с LLM = профиль `office-full` ([CANONICAL-RUNTIME.md](CANONICAL-RUNTIME.md)). Отдельный прогон — **CANONICAL SCENARIO v1.1** после успеха v1. |


---

## 2. Подготовка среды (перед Telegram)

### 2.1 Где запускать

Рекомендуется **тот же контур**, которым пользуетесь в работе: **сервер (docker compose)** или **локально** (Python + Postgres/SQLite). Главное — доступный **Telegram-бот** и **DASHBOARD_URL** в `.env`, чтобы ссылки в ответах были верны.

### 2.2 Переменные окружения (минимум)

Скопируйте `.env.example` → `.env` и заполните:

- `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID` — бот и ваш чат.
- `OWNER_API_KEY` — обязателен (fail-fast).
- `POSTGRES_PASSWORD` и строка БД — если compose с Postgres.
- `DASHBOARD_URL` — URL, по которому открываете Dashboard (например `https://agm.mywavetreaning.ru` или `http://localhost:8080`).

Для **office-lite** при использовании compose **не задавайте** `ORCHESTRATION_ENGINE=auto` в `.env`, если не переопределяете образ: compose подставляет `rule_based` по умолчанию (см. `docker-compose.yml`).

### 2.3 Запуск

```bash
docker compose build --no-cache app
docker compose up -d
```

Проверка: `GET /api/system/health` с заголовком `X-API-Key: <OWNER_API_KEY>` → `status` не `error`.

Точка входа процесса: `python -m app.main` (в compose: после `alembic upgrade head`).

---

## 3. Сценарий по шагам (что делает оператор)

### Шаг A — Intake

1. Откройте диалог с ботом **с того же `OWNER_CHAT_ID`**, что в `.env`.
2. Отправьте сообщение **строго в формате intake** (см. `app/bot/handlers.py`):

```text
#TASK Тест CANONICAL SCENARIO v1: кратко описать план проверки API лимитов без деплоя в прод.
```

(Текст можно заменить; важно начало `#TASK`.)

3. Ожидайте ответ: «Принято. Миссия #… в работе».

### Шаг B — Orchestration

Оркестрация запускается в фоне: `run_sync_orchestration` (`app/orchestrator/sync_run.py`), тот же путь, что API.

Подождите сообщение с итогом (может занять от секунд до минут в зависимости от объёма pipeline и диска).

### Шаг C — Approve (если появилось)

Если финальный статус `WAIT_OWNER`, в Telegram придёт текст про апрув и **кнопки** (`build_owner_buttons` в `handlers.py`). Нажмите **Approve** (или согласованное действие по сценарию).

Если статус сразу `DONE` (задача не требует approve), шаг C пропускается — валидный исход для v1.

### Шаг D — Результат

- **Telegram:** итоговое сообщение с `summary` и ссылкой на Dashboard. Ссылка содержит подписанный параметр **`?link=`** (`app/shared/dashboard_link.py`) — страницу **`/tasks/{id}`** можно открыть в браузере **без** `X-API-Key`. Срок жизни: `DASHBOARD_LINK_TTL_SECONDS` (по умолчанию 1 ч). Кнопка **«📊 Dashboard»** в том же сообщении ведёт на тот же URL.
- **Диск:** артефакты по умолчанию:
  - В репозитории / bind-mount: `app/artifacts/tasks/task_<task_id>/`
  - Внутри контейнера: `/app/app/artifacts` (см. `docker-compose.yml` volume).
  Типичные подпапки: `court/` (финальный отчёт), `handoffs/` — см. фактическую структуру после прогона.

---

## 4. Отчёт о прогоне — **ЗАПОЛНЕНО** (живой Telegram, 2026-04-12)

| Поле | Значение |
|------|----------|
| **Сценарий** | CANONICAL SCENARIO v1 |
| **Профиль** | office-lite (`ORCHESTRATION_ENGINE=rule_based`, образ без CrewAI) |
| **task_id** | **8** (`mission_id` = task_id) |
| **Дата / время** | **2026-04-12**, приём задачи **16:55**, ответы бота **~02:27–02:28** (локальное время со скрина оператора) |
| **Где запускалось** | Хост приложения в LAN: **`192.1.1.11:8080`**; клиент: **Telegram Desktop (Windows)**; бот **MyWave_AI_Team** |
| **Вход (текст #TASK)** | `#TASK Тест CANONICAL SCENARIO v1: кратко описать план проверки API лимитов без деплоя в прод.` |
| **Финальный статус (на момент фиксации)** | **WAIT_OWNER** — оркестрация завершена, открыт **Owner approval gate** («нужен апрув для EXECUTE») |
| **Был ли approve** | **Не зафиксирован в этом отчёте** (на скрине показаны кнопки **Approve / Rework / Clarify / Full report**; после нажатия Approve при необходимости дополните таблицу ниже) |
| **Кратко: что произошло** | Intake принят → фоновый `run_sync_orchestration` → пройдены этапы **triage → pipeline → roundtable → court**; в сводке: домен product dev / feature delivery, **6 handoffs**, **2 риска**; статус **ожидает решения владельца**; ссылка на Dashboard и синхронизация Telegram/Dashboard как точек входа. |
| **Результат для пользователя** | Сообщение «Принято. Миссия #8…»; затем итог с summary, отчёт по контуру, ссылка `http://192.1.1.11:8080/tasks/8`, интерактивные кнопки для решения. |
| **Путь к артефактам** | От корня деплоя / репозитория на машине с volume: **`app/artifacts/tasks/task_8/`** (подпапки `court/`, `handoffs/` и др. по факту) |
| **Проверено Dashboard** | **Да** — `http://192.1.1.11:8080/tasks/8` |

### Дополнение после нажатия Approve (опционально)

| Поле | Значение |
|------|----------|
| **Статус после approve** | *обновить: например APPROVED_WAIT_MERGE / DONE* |
| **Дата/время** | *обновить* |
| **Финальное сообщение в Telegram** | *кратко* |

### Подпись закрытия сценария v1 (цикл до гейта + артефакты)

> **AI Office v1 (office-lite): единый цикл intake → orchestration → план/артефакты → гейт WAIT_OWNER подтверждён прогоном от 2026-04-12, task_id 8.**  
> Завершение сценария «с нажатием Approve и финальным статусом» — зафиксировать в строках таблицы «Дополнение после Approve».

---

## 5. Если сценарий не прошёл

Заполните:


| Поле                              | Значение                                                        |
| --------------------------------- | --------------------------------------------------------------- |
| **Точка разрыва**                 | *[intake / оркестрация / Telegram ответ / артефакты / approve]* |
| **Симптом / лог**                 | *[сообщение об ошибке, traceback, код HTTP]*                    |
| **Вероятная причина**             | *[секреты, OWNER_CHAT_ID, БД, таймаут, диск]*                   |
| **Оценка времени на исправление** | *[часы / дни — по месту]*                                       |


Типичные разрывы:

- **Доступ только для Owner** — `OWNER_CHAT_ID` не совпадает с чатом.
- **БД** — миграции не применены, `DATABASE_URL` неверен.
- **Оркестрация** — исключение в `run_sync_orchestration`; смотреть логи контейнера `app` и audit events.

---

## 6. Связь с кодом (без новых фич)


| Этап            | Файл / модуль                                                      |
| --------------- | ------------------------------------------------------------------ |
| Intake          | `app/bot/handlers.py` — `handle_task_intake`, `_run_orchestration` |
| Оркестрация     | `app/orchestrator/sync_run.py`                                     |
| Артефакты court | `app/orchestrator/court.py` — `ARTIFACTS_DIR` / `tasks/task_{id}`  |
| Approve UI TG   | `handlers.py` — `handle_owner_callback`, `build_owner_buttons`     |


---

## 7. Следующий шаг после успеха v1

Только после заполненного раздела 4:

- зафиксировать **CANONICAL SCENARIO v1.1 (office-full)** при необходимости LLM;
- затем — развитие ролей/UI по отдельным задачам.

---

*Версия документа: 1.1 — 2026-04-12 (заполнен отчёт о живом прогоне task_id=8)*