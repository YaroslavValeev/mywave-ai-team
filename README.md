# MyWave AI-TEAM MVP v0

**AI Office System** — control-plane: Telegram → задача → оркестрация по ролям → approve → артефакты.  
**Канон runtime, профили `office-full` / `office-lite`, границы MVP:** [docs/CANONICAL-RUNTIME.md](docs/CANONICAL-RUNTIME.md).  
**Первый живой сценарий (Telegram → артефакты):** [docs/CANONICAL-SCENARIO-V1.md](docs/CANONICAL-SCENARIO-V1.md).

Иерархическая multi-agent система **«Конвейер → Круглый стол → Суд (AGM)»** для MyWave.

- **Среда:** timeweb.cloud
- **Оркестрация:** CrewAI (prod-ориентированно)
- **Канал:** Telegram bot DM (aiogram) + минимальный Dashboard
- **Режим:** semi-autonomous — CRITICAL EXECUTE только после Approve Owner

## Структура проекта

```
app/
  bot/           # aiogram: intake #TASK, кнопки, redaction middleware
  orchestrator/  # AGM: triage, pipeline, roundtable, court
  storage/       # SQLAlchemy + миграции
  dashboard/     # FastAPI + Jinja
  gateway/       # (v1.2) секреты, capabilities, dangerous actions
  mcp_server/    # (v1.2) private MCP tools для Cursor/агентов
  runners/       # (v1.2) Cursor CLI runner
  config/        # routing, policy, telegram, owner_config, skills_allowlist, automation_triggers, mcp_tools
  artifacts/     # генерация .md
  shared/        # audit, critical_flags
skills/          # (v1.2) локальные skills (allowlist)
tests/
docker-compose.yml
Dockerfile
```

## Локальный запуск (без Caddy)

Для разработки — app слушает 8080 напрямую. Добавь в `docker-compose.override.yml`:

```yaml
services:
  app:
    ports: ["8080:8080"]
```

Затем:
```bash
cp .env.example .env
# DASHBOARD_URL=http://localhost:8080
# Заполнить TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID, POSTGRES_PASSWORD, OWNER_API_KEY
docker compose up -d
# Dashboard: http://localhost:8080 (заголовок X-API-Key)
```

## Деплой agm.mywavetreaning.ru (production)

Caddy: reverse proxy + HTTPS + BasicAuth. Порт 8080 не публикуется.

**Подробно:** [docs/DEPLOY-agm.mywavetreaning.ru.md](docs/DEPLOY-agm.mywavetreaning.ru.md)

Кратко:
1. DNS: A-запись `agm` → IP сервера timeweb
2. Порты 80/443 открыты
3. `cp Caddyfile.example Caddyfile`, в `Caddyfile` заменить `<BASICAUTH_HASH>` (см. `caddy hash-password`)
4. `.env`: OWNER_API_KEY, DASHBOARD_URL=https://agm.mywavetreaning.ru
5. `docker compose up -d`
6. Вход: https://agm.mywavetreaning.ru/tasks (логин `owner` + пароль)

## Smoke test

```bash
pip install -r requirements.txt pytest
pytest tests/ -v
```

Ожидаемый результат (HF-4: 0 skipped):
- SQLite in-memory для smoke-тестов
- `pytest -q` → все тесты проходят без skipped

## Intake

Сообщение в Telegram, начинающееся с `# TASK` или `#TASK` → создаётся задача, запускается оркестрация.

### Smart Intake v0

- Свободный текст (не `#TASK`), голос (при `OPENAI_API_KEY` + Whisper) и фото **с подписью** проходят через нормализацию; перед созданием миссии Owner подтверждает кнопками в Telegram.
- Подтверждённые черновики вызывают тот же путь, что и `#TASK`: `create_task` + полный оркестратор.
- Дополнение к существующей миссии: ответ реплаем на сообщение с «Миссия #N» → ветка **attach** (дописывает `owner_text`, без автозапуска оркестра).
- **HTTP:** `POST /api/intake/normalize` — тот же заголовок `X-API-Key`, тело JSON как у `NormalizeIntakeRequest`; ответ — нормализованный `task_brief` и `decision` (задача **не** создаётся).
- **Env:** `INTAKE_USE_LLM=true` — один структурированный вызов LLM к OpenAI (иначе только правила); `INTAKE_PENDING_TTL_SEC` — TTL черновиков с кнопками в памяти процесса бота (по умолчанию 900).

### Smart Intake v1 (контекст и память)

- При передаче `repo` в `normalize_intake` (Telegram и `POST /api/intake/normalize`) включается слой **v1** (отключить: `INTAKE_V1=false`).
- **Проект:** эвристика по названию/slug в тексте, `project_id_hint` в API, реплай к миссии → проект задачи; при нескольких совпадениях — `decision=clarify` со списком проектов.
- **Продолжение vs новая:** `task_matcher` + фразы («добавь к задаче», …) и порог Jaccard по открытым задачам (`INTAKE_ATTACH_SIMILARITY_THRESHOLD`, по умолчанию ~0.26).
- **Память:** чтение последних `MemoryEntry` проекта в `task_brief.memory_refs` / `context_summary`; запись снимка после оркестрации — `write_task_memory_after_orchestration` (`INTAKE_MEMORY_WRITE=false` чтобы выключить).
- Расширенный ответ API: `matched_project_id`, `matched_task_id`, `similarity_score`, `decision_reason`, `memory_used`. В `TaskBrief`: `project_id`, `related_task_id`, `memory_refs`, `context_summary`.
- Отдельные таблицы **TaskLink / ContextEdge** в v1 не вводились: связи задача↔проект и память покрываются `Task.project_id` и `MemoryEntry`.

## Конфигурация

- `app/config/owner_config.yaml` — OWNER-CONFIG (домены, лимиты, метрики)
- `app/config/routing.yaml` — маршрутизация по доменам
- `app/config/policy.yaml` — критичность, лимиты, безопасность
- `app/config/telegram.yaml` — кнопки, callbacks (или .env)
- `app/config/skills_allowlist.yaml` — (v1.2) allowlist skills
- `app/config/automation_triggers.yaml` — (v1.2) webhooks, schedule
- `app/config/mcp_tools.yaml` — (v1.2) MCP tools config

Дополнительные env-флаги:

- `ORCHESTRATION_ENGINE=auto|crewai|rule_based` — по умолчанию **auto** (роли CrewAI + STEP_PROFILES, при недоступности — fallback); **rule_based** — только правила, без LLM
- `ORCHESTRATION_ALLOW_FALLBACK=true|false` — разрешить fallback на rule-based слой
- `CREWAI_MODEL`, `CREWAI_PROVIDER`, `CREWAI_TEMPERATURE`, `CREWAI_TIMEOUT`, `CREWAI_MAX_TOKENS` — runtime config для CrewAI bridge
- `TELEGRAM_RETRY_ATTEMPTS` и `TELEGRAM_RETRY_BASE_SECONDS` — retry/backoff для Telegram send
- `RETENTION_DAYS` — retention cleanup для старых задач и orphan audit events
- `INTAKE_USE_LLM`, `INTAKE_LLM_MODEL`, `INTAKE_PENDING_TTL_SEC` — Smart Intake (см. выше)
- `INTAKE_V1`, `INTAKE_ATTACH_SIMILARITY_THRESHOLD`, `INTAKE_MEMORY_WRITE` — Smart Intake v1 (контекст/память)

## Dashboard Auth (HF-1)

- Все эндпоинты (кроме `/health`) требуют заголовок `X-API-Key: <OWNER_API_KEY>`
- Без `OWNER_API_KEY` в .env приложение не стартует (fail-fast)

## v1.2 — Gateway, MCP, Runners

- [docs/MCP.md](docs/MCP.md) — подключение MCP tools к Cursor
- [docs/CURSOR-RUNNER.md](docs/CURSOR-RUNNER.md) — локальный PR-loop и вызов Cursor CLI (машина Owner; сервер отдаёт API, merge — вручную)
- [docs/SECURITY-SKILLS.md](docs/SECURITY-SKILLS.md) — политика skills (allowlist)

## Maintenance

- Retention cleanup: `python scripts/run_retention.py`
- E2E API flow покрыт тестом `tests/test_e2e_api_flow.py`
- CrewAI роли (pipeline/triage) используются при `auto` или `crewai`; нужны `crewai` в зависимостях и ключ/API (см. `.env.example`, `CREWAI_MODEL` / `CREWAI_DEFAULT_MODEL`)
- HTML-страницы `/tasks/{id}` и связанные GET: доступ по **`?link=`** из Telegram (HMAC, см. `app/shared/dashboard_link.py`) или по `api_key` / `X-API-Key`; **`/api/*`** — только с ключом.
- System health: `GET /api/system/health`
- Manual merge confirmation: `POST /api/tasks/{id}/merged`

## Next

- Подключить реальный production provider/runtime для CrewAI и проверить на живом окружении
- Добавить более детальный health/failure reporting по внешним интеграциям
- Расширить E2E до Telegram/Runner/manual merge сценария
