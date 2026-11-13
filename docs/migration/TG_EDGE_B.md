# TG Edge B — polling на EU/tourism

## Зачем
С RU (`62.113.42.227`) до EU SOCKS/WG не проходит TCP/UDP (ICMP проходит).
Dashboard на `https://agm.mywavewake.ru` жив с `TELEGRAM_POLLING_ENABLED=false`.

Edge-бот на хосте с доступом к Telegram (EU `72.56.99.214` или tourism `5.129.249.113`):
- принимает `#TASK` / кнопки в Telegram
- создаёт/ведёт миссии через Control API на `agm.mywavewake.ru`
- SoT, артефакты, orchestration остаются на RU

## На RU (уже сделано)
- `TELEGRAM_POLLING_ENABLED=false`
- health `ok`, migration `007`

## На EU (`shared-eu-socks`) — установка

```bash
mkdir -p /opt/mywave/tg-edge && cd /opt/mywave/tg-edge
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Скопировать сюда `api_edge_bot.py` и `requirements.txt` из репо
`scripts/tg_edge/`.

Создать `/opt/mywave/tg-edge/.env` (секреты не коммитить):

```bash
TELEGRAM_BOT_TOKEN=...
OWNER_CHAT_ID=510686579
OWNER_API_KEY=...          # тот же, что на RU
DASHBOARD_URL=https://agm.mywavewake.ru
AGENTS_CONTROL_API_URL=https://agm.mywavewake.ru
```

Проверка API с EU:

```bash
set -a; source .env; set +a
curl -sS -H "X-API-Key: $OWNER_API_KEY" "$AGENTS_CONTROL_API_URL/api/system/health"
```

Запуск:

```bash
cd /opt/mywave/tg-edge
. .venv/bin/activate
set -a; source .env; set +a
python api_edge_bot.py
```

systemd (опционально):

```bash
cat >/etc/systemd/system/mywave-tg-edge.service <<'EOF'
[Unit]
Description=MyWave Telegram Edge → agm.mywavewake.ru
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/mywave/tg-edge
EnvironmentFile=/opt/mywave/tg-edge/.env
ExecStart=/opt/mywave/tg-edge/.venv/bin/python /opt/mywave/tg-edge/api_edge_bot.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now mywave-tg-edge.service
systemctl status mywave-tg-edge.service --no-pager
```

## Проверка Owner
В TG: `#TASK проверка edge prod`  
Ожидание: ответ edge + миссия в `https://agm.mywavewake.ru/tasks`

## Откат
```bash
systemctl disable --now mywave-tg-edge.service
# RU остаётся с polling=false и рабочей панелью
```

## Позже
Когда RU→EU TCP/UDP починят — можно вернуть polling на RU и выключить edge.
