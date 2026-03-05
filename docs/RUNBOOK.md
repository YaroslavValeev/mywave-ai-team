# MyWave AI-TEAM — Runbook

Операционные процедуры при типичных сбоях и вопросах.

## 502 Bad Gateway

**Симптом:** браузер или curl возвращает 502 при обращении к agm.mywavetreaning.ru.

**Действия:**
1. Проверить статус контейнеров: `docker compose ps`
2. Логи Caddy: `docker compose logs caddy`
3. Логи app: `docker compose logs app`
4. Если app не запущен — проверить Postgres: `docker compose logs postgres`
5. Если БД не инициализирована: `docker compose up -d postgres` → подождать healthcheck → `docker compose up -d app caddy`

## SSL / TLS ошибки

**Симптом:** браузер ругается на сертификат или HTTPS не работает.

1. Проверить DNS: `nslookup agm.mywavetreaning.ru` — IP должен быть сервера.
2. Порты 80/443 открыты: `sudo ufw status` или панель timeweb.
3. Логи Caddy: `docker compose logs caddy` — ошибки Let's Encrypt.
4. При rate-limit Let's Encrypt — подождать или использовать staging: `tls internal` в Caddyfile (временно).

## .env / переменные окружения

**Симптом:** приложение не стартует с "OWNER_API_KEY must be set" или похожими ошибками.

1. Убедиться, что `.env` существует в корне проекта.
2. Проверить: `OWNER_API_KEY`, `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `POSTGRES_PASSWORD` заполнены.
3. Нет пробелов вокруг `=`: `KEY=value`, не `KEY = value`.

## База данных (Postgres)

**Симптом:** app падает с "connection refused" к postgres.

1. `docker compose ps` — postgres должен быть Up (healthy).
2. `docker compose logs postgres` — ошибки инициализации.
3. Проверить `POSTGRES_PASSWORD` в `.env` совпадает с тем, что в `docker-compose.yml`.
4. При необходимости пересоздать: `docker compose down -v` (осторожно — удалит данные), затем `docker compose up -d`.

## Бэкапы (daily 7/30)

Рекомендация (см. OWNER-DECISIONS): daily backups, retention 7 дней + 4 недельных (30 дней).

Пример cron на сервере:
```bash
# Ежедневно в 03:00
0 3 * * * docker compose exec -T postgres pg_dump -U mywave mywave_ai | gzip > /backups/mywave_ai_$(date +\%Y\%m\%d).sql.gz
```

Ротация: удалять файлы старше 7 дней, кроме одного в неделю (воскресенье) — хранить 4 недели.
