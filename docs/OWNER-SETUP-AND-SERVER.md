# Owner Setup and Server — пошаговый playbook

Документ для владельца: где взять секреты, как заполнить `.env`, точные команды на сервере и критерий готовности **10/10**.

Связанные документы:

- [DEPLOY-agm.mywavetreaning.ru.md](DEPLOY-agm.mywavetreaning.ru.md) — краткий deploy
- [CANONICAL-RUNTIME.md](CANONICAL-RUNTIME.md) — профили office-lite / office-full
- [RUNBOOK.md](RUNBOOK.md) — типичные сбои

---

## 1. Таблица секретов: где взять и куда вписать

Копируйте значения **только в `.env`** (файл в `.gitignore`). Не коммитьте секреты.

### 1.1 Обязательные (без них prod не стартует)

| Переменная | Где взять | Как установить |
|------------|-----------|----------------|
| `TELEGRAM_BOT_TOKEN` | Telegram → [@BotFather](https://t.me/BotFather) → `/mybots` → ваш бот → **API Token** (или `/newbot`) | `.env`: `TELEGRAM_BOT_TOKEN=123456:ABC...` |
| `OWNER_CHAT_ID` | Напишите [@userinfobot](https://t.me/userinfobot) или [@getidsbot](https://t.me/getidsbot) → **Id** | `.env`: `OWNER_CHAT_ID=123456789` (число) |
| `OWNER_API_KEY` | Сгенерировать сами | Windows PowerShell: `[Convert]::ToBase64String((1..32\|%{Get-Random -Max 256}\|%{ [byte]$_ }))`; Linux: `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Сгенерировать сами | `openssl rand -hex 16` → один и тот же пароль в `.env` на сервере |

### 1.2 Обязательные для HTTPS Dashboard

| Данные | Где взять | Как установить |
|--------|-----------|----------------|
| DNS A `agm` → IP сервера | Панель DNS `mywavetreaning.ru` (timeweb) | A-запись `agm` = публичный IP VPS |
| BasicAuth пароль Caddy | Придумать сильный пароль | `docker run --rm caddy:2 caddy hash-password --plaintext "ВАШ_ПАРОЛЬ"` → hash в `Caddyfile` |
| `DASHBOARD_URL` | Фиксированный | `DASHBOARD_URL=https://agm.mywavetreaning.ru` |

### 1.3 Опциональные (office-full / LLM / runner)

| Переменная | Где взять | Зачем |
|------------|-----------|-------|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | CrewAI, Smart Intake LLM, Whisper |
| `ORCHESTRATION_ENGINE` | В `.env` | `auto` для office-full, `rule_based` для lite |
| `CREWAI_DEFAULT_MODEL` | Обычно `gpt-4o-mini` | Модель ролей pipeline |
| `GH_TOKEN` / `GITHUB_TOKEN` | GitHub → Settings → Developer settings → PAT | Cursor PR loop |
| `GITHUB_REPOSITORY` | `owner/repo` | PR loop |
| `DASHBOARD_LINK_SECRET` | `openssl rand -hex 32` | Отдельный HMAC для `?link=` (опционально) |
| `DOCKER_BUILD_TARGET` | `lite` или `full` | Профиль Docker-образа (см. раздел 3) |

---

## 2. Локальная проверка: что уже заполнено

На Windows (показывает только **имена** ключей, не значения):

```powershell
cd c:\ProjectMyWave\MyWave_AI_TEAM_Presets_v1_1
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([A-Z0-9_]+)=(.*)$' -and $matches[2].Trim() -ne '') { $matches[1] }
}
```

Минимум для старта: `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `OWNER_API_KEY`, `POSTGRES_PASSWORD`.

Скопировать на сервер:

```powershell
scp .env user@SERVER_IP:/path/to/MyWave_AI_TEAM_Presets_v1_1/.env
```

---

## 3. Профили Docker на сервере

| Цель | Команда сборки | `.env` |
|------|----------------|--------|
| **office-lite** (default, без CrewAI) | `docker compose up -d --build` | `ORCHESTRATION_ENGINE=rule_based` |
| **office-full** (CrewAI + LLM) | `DOCKER_BUILD_TARGET=full docker compose up -d --build` | `ORCHESTRATION_ENGINE=auto`, `OPENAI_API_KEY=...` |

Подробнее: [CANONICAL-RUNTIME.md](CANONICAL-RUNTIME.md).

---

## 4. Топология MyWave (подтверждено Owner)

| Роль | Хост | IP | Назначение |
|------|------|-----|------------|
| **App + Dashboard + Postgres + Caddy** | mywave-bot-server | `62.113.42.227` | `agm.mywavetreaning.ru`, сайт, боты в своих папках |
| **EU Telegram bridge** | Friendly Cygnus | `72.56.99.214` | Доступ к Telegram API из РФ без VPN на клиенте |
| DNS A `agm` | → | `62.113.42.227` | Панель DNS `mywavetreaning.ru` |

`DASHBOARD_URL=https://agm.mywavetreaning.ru`

Telegram polling с RU-сервера: задайте `TELEGRAM_PROXY_URL` на socks5/http **к мосту** (порт — тот, что настроен на 72.56.99.214). Если мост уже проброшен на localhost RU-машины — `socks5://127.0.0.1:PORT`.

### LLM: локальный → облако

1. Если на сервере (или рядом) есть Ollama/LM Studio — `OPENAI_BASE_URL=http://127.0.0.1:11434/v1`, `OPENAI_API_KEY=ollama`, модель локальная.
2. Иначе — облачный `OPENAI_API_KEY` + `CREWAI_MODEL=gpt-4.1-nano`.
3. `ORCHESTRATION_ALLOW_FALLBACK=true` — при сбое LLM контур не падает (rule-based).

Код уже читает `OPENAI_BASE_URL` / `CREWAI_BASE_URL` в `app/orchestrator/crewai_bridge.py`.

## 5. Точные команды на сервере (RU + nginx, без Caddy)

**Факты (июль 2026):** на `62.113.42.227` уже nginx (mywavewake). Docker изначально не установлен. EU-мост: SOCKS5 `72.56.99.214:1080` (3proxy, auth strong). Caddy на 80/443 **не использовать**.

### 5.0 DNS (панель timeweb / DNS домена **mywavewake.ru**)

A-запись: `agm` → `62.113.42.227`  
Итоговый хост: **`agm.mywavewake.ru`** (не `mywavetreaning.ru` — это устаревшее имя из старых docs).

Проверка: `nslookup agm.mywavewake.ru` → должен показать `62.113.42.227`.

`DASHBOARD_URL=https://agm.mywavewake.ru`

### 5.1 Telegram proxy (проверено)

```bash
TELEGRAM_PROXY_URL=socks5://YaroslavValeev:MyWaveParser2026@72.56.99.214:1080
```

### 5.2 Deploy на RU `ssh root@62.113.42.227`

```bash
# 0) Docker (если ещё нет)
apt-get update
apt-get install -y docker.io docker-compose-v2
systemctl enable --now docker
docker --version

# 1) Папка + клон
mkdir -p /opt/mywave/ai-team
cd /opt/mywave/ai-team
git clone https://github.com/YaroslavValeev/mywave-ai-team.git .
# или SSH: git clone git@github.com:YaroslavValeev/mywave-ai-team.git .

# 2) .env
cp .env.example .env
nano .env
# См. блок переменных ниже

# 3) App+Postgres на 127.0.0.1:8080 (Caddy отключён профилем)
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.server.yml ps
docker compose -f docker-compose.yml -f docker-compose.server.yml logs -f app

# 4) nginx vhost
cp deploy/nginx-agm.mywavetreaning.ru.conf /etc/nginx/sites-available/agm.mywavetreaning.ru
ln -sf /etc/nginx/sites-available/agm.mywavetreaning.ru /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d agm.mywavetreaning.ru

# 5) Проверки
curl -s -H "X-API-Key: ВАШ_OWNER_API_KEY" https://agm.mywavetreaning.ru/api/system/health
# Telegram: #TASK Проверка prod 10/10
```

Минимум в `.env`:

```bash
TELEGRAM_BOT_TOKEN=...
OWNER_CHAT_ID=510686579
OWNER_API_KEY=...
POSTGRES_PASSWORD=...
DASHBOARD_URL=https://agm.mywavetreaning.ru
DASHBOARD_LINK_SECRET=...
TELEGRAM_PROXY_URL=socks5://YaroslavValeev:MyWaveParser2026@72.56.99.214:1080
GITHUB_REPOSITORY=YaroslavValeev/mywave-ai-team
ORCHESTRATION_ENGINE=rule_based
```

Для office-full: `DOCKER_BUILD_TARGET=full`, `ORCHESTRATION_ENGINE=auto`, `OPENAI_API_KEY`, `CREWAI_MODEL=gpt-4.1-nano`.

### Rollback

```bash
docker compose down
# git checkout <previous_commit>
docker compose up -d --build
```

**Осторожно:** `docker compose down -v` удаляет том Postgres с данными.

---

## 6. Чеклист готовности 10/10

### Код (агенты / CI)

- [ ] Миграция `007_intake_drafts` применена (`alembic upgrade head`)
- [ ] Smart Intake drafts переживают рестарт бота (таблица `intake_drafts`)
- [ ] `pytest tests/ -q` — все тесты зелёные
- [ ] Docker target `lite` и `full` собираются

### Владелец (сервер)

- [ ] `.env`: `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `OWNER_API_KEY`, `POSTGRES_PASSWORD`, `DASHBOARD_URL`
- [ ] DNS `agm.mywavetreaning.ru` → IP сервера
- [ ] `Caddyfile` с bcrypt hash (не коммитить)
- [ ] `curl` HTTPS: 401 без auth, 200 с BasicAuth на `/tasks`
- [ ] `GET /api/system/health` с `X-API-Key` → OK
- [ ] Telegram `#TASK` → оркестрация → **WAIT_OWNER** + кнопки

### Опционально (office-full)

- [ ] `DOCKER_BUILD_TARGET=full`, `OPENAI_API_KEY`, `ORCHESTRATION_ENGINE=auto`
- [ ] Health показывает orchestration engine `auto` / crewai available

---

## 7. Типичные ошибки

| Симптом | Решение |
|---------|---------|
| `OWNER_API_KEY must be set` | Заполнить `OWNER_API_KEY` в `.env`, перезапустить `docker compose up -d` |
| `DB init failed` | `docker compose logs postgres`; дождаться healthy; `alembic upgrade head` |
| 401 на API | Заголовок `X-API-Key: <OWNER_API_KEY>` |
| Бот молчит | Проверить `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID` (ваш chat id) |
| Smart Intake «Сессия истекла» сразу | Проверить миграцию 007; `docker compose logs app` на ошибки БД |
| CrewAI не работает | Образ `full` + `OPENAI_API_KEY` + `ORCHESTRATION_ENGINE=auto` |

---

## 8. Maintenance

```bash
# Retention (старые задачи)
docker compose exec app python scripts/run_retention.py

# Backup Postgres (если настроен cron)
./scripts/backup_postgres.sh /backups
```

См. [RUNBOOK.md](RUNBOOK.md) для 502, SSL и restore.
