# MyWave AI-TEAM MVP v0

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
  config/        # routing.yaml, policy.yaml, telegram.yaml, owner_config.yaml
  artifacts/     # генерация .md
  shared/        # audit, critical_flags
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
3. `Caddyfile`: заменить `<BASICAUTH_HASH>` (см. `caddy hash-password`)
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

## Конфигурация

- `app/config/owner_config.yaml` — OWNER-CONFIG (домены, лимиты, метрики)
- `app/config/routing.yaml` — маршрутизация по доменам
- `app/config/policy.yaml` — критичность, лимиты, безопасность
- `app/config/telegram.yaml` — кнопки, callbacks (или .env)

## Dashboard Auth (HF-1)

- Все эндпоинты (кроме `/health`) требуют заголовок `X-API-Key: <OWNER_API_KEY>`
- Без `OWNER_API_KEY` в .env приложение не стартует (fail-fast)

## TODO v0.1

- CrewAI full integration: заменить stub triage/pipeline на реальные flows
- Retention job: удаление записей старше 90 дней
- Telegram retry: экспоненциальный retry при ошибках
- E2E test: полный цикл #TASK → Court → Approve
