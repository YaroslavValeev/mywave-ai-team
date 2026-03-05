# Деплой agm.mywavetreaning.ru — «под ключ»

## 1) DNS

В панели DNS домена `mywavetreaning.ru`:

| Тип | Имя | Значение | TTL |
|-----|-----|----------|-----|
| A | agm | SERVER_PUBLIC_IP | 300 |

**Проверка:**
```powershell
nslookup agm.mywavetreaning.ru
# IP должен совпадать с IP сервера
```

## 2) Порты 80/443

На сервере:
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

Либо в панели timeweb.cloud → firewall: открыть 80 и 443.

## 3) Caddy + BasicAuth

### 3.1 Сгенерировать хэш пароля

```bash
docker run --rm caddy:2 caddy hash-password --plaintext "ТВОЙ_СИЛЬНЫЙ_ПАРОЛЬ"
```

Скопировать вывод (bcrypt hash).

### 3.2 Создать Caddyfile (боевой файл не в репо)

```bash
cp Caddyfile.example Caddyfile
```

Заменить `<BASICAUTH_HASH>` в `Caddyfile` на полученный хэш (см. п. 3.1).

### 3.3 .env на сервере

```
OWNER_API_KEY=длинный_уникальный_ключ
TELEGRAM_BOT_TOKEN=...
OWNER_CHAT_ID=...
POSTGRES_PASSWORD=...
DASHBOARD_URL=https://agm.mywavetreaning.ru
```

## 4) Запуск

```bash
docker compose up -d --build
docker compose logs -f caddy
```

Caddy автоматически получит TLS-сертификат (Let's Encrypt).

## 5) Проверки

```bash
# HTTPS + BasicAuth
curl -I https://agm.mywavetreaning.ru
# 401 — просит авторизацию

curl -I -u owner:ТВОЙ_ПАРОЛЬ https://agm.mywavetreaning.ru/tasks
# 200

# Порт 8080 НЕ торчит наружу
ss -tulpn | grep 8080
# Должно быть пусто или только 127.0.0.1
```

## 6) Вход в браузере

1. Открыть https://agm.mywavetreaning.ru/tasks
2. Логин: `owner`, пароль: тот, что задали в hash-password
3. X-API-Key прокидывается Caddy автоматически — вручную ничего не нужно

## 7) Ссылки в Telegram

Кнопка "Dashboard" в сообщениях бота ведёт на:
- https://agm.mywavetreaning.ru/tasks
- https://agm.mywavetreaning.ru/tasks/{task_id}
