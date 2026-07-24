# LLM tier: local (RU) + OpenAI via EU

См. [ADR-006](../decisions/ADR-006-llm-tier-local-eu.md).

| Tier | Назначение | Endpoint |
|------|------------|----------|
| `local` | обычные миссии | Ollama / LM Studio на RU |
| `cloud` | сложные / Owner GO | LiteLLM на EU `72.56.99.214:4000` → OpenAI |

Переключение: `#CLOUD` / `#OPENAI` в тексте задачи, или кнопка **🧠 OpenAI (EU)** в Telegram.

---

## A) EU — LiteLLM (Owner, `ssh root@72.56.99.214`)

Выполняй **по одной команде** (не вставляй целые блоки с комментариями в одну строку).

```bash
apt update && apt install -y python3 python3-venv python3-pip ufw
```

```bash
useradd -r -s /usr/sbin/nologin litellm 2>/dev/null || true
mkdir -p /etc/litellm /var/log/litellm
chown litellm:litellm /var/log/litellm
```

```bash
python3 -m venv /opt/litellm-venv
/opt/litellm-venv/bin/pip install --upgrade pip 'litellm[proxy]'
```

```bash
openssl rand -hex 32
```
Сохрани вывод как `LITELLM_MASTER_KEY` (например `sk-` + hex).

Создай `/etc/litellm/env` (права 600) с реальными ключами **только на EU**:

```bash
cat > /etc/litellm/env <<'EOF'
OPENAI_API_KEY=sk-proj-REPLACE_ME
LITELLM_MASTER_KEY=sk-REPLACE_WITH_OPENSSL_HEX
EOF
chmod 600 /etc/litellm/env
```

```bash
cat > /etc/litellm/config.yaml <<'EOF'
model_list:
  - model_name: gpt-4.1-nano
    litellm_params:
      model: openai/gpt-4.1-nano
      api_key: os.environ/OPENAI_API_KEY
  - model_name: gpt-4o-mini
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
EOF
```

```bash
cat > /etc/systemd/system/litellm.service <<'EOF'
[Unit]
Description=LiteLLM MyWave OpenAI proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
EnvironmentFile=/etc/litellm/env
ExecStart=/opt/litellm-venv/bin/litellm --config /etc/litellm/config.yaml --host 0.0.0.0 --port 4000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now litellm
systemctl status litellm --no-pager
```

Firewall — только RU:

```bash
ufw allow from 62.113.42.227 to any port 4000 proto tcp comment 'MyWave RU LiteLLM'
ufw status numbered
```

Smoke на EU:

```bash
set -a; source /etc/litellm/env; set +a
curl -sS http://127.0.0.1:4000/health
curl -sS http://127.0.0.1:4000/v1/models -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

---

## B) RU — Ollama (local tier) + env (Owner, `/opt/mywave/ai-team`)

```bash
cd /opt/mywave/ai-team
```

Ollama в Docker (лёгкая модель; при нехватке RAM — `llama3.2:3b`):

```bash
docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml -f docker-compose.ollama.yml --profile molt up -d

docker exec ai-team-ollama-1 ollama pull llama3.2:3b
```

Правки `.env` (подставь свой `LITELLM_MASTER_KEY` с EU; **не** клади sk-proj OpenAI на RU):

```bash
# удалить старые дубликаты ключей tier
sed -i '/^LLM_TIER_DEFAULT=/d;/^LLM_LOCAL_/=d;/^LLM_CLOUD_/=d' .env

cat >> .env <<'EOF'
LLM_TIER_DEFAULT=local
LLM_LOCAL_BASE_URL=http://ollama:11434/v1
LLM_LOCAL_API_KEY=ollama
LLM_LOCAL_MODEL=llama3.2:3b
LLM_CLOUD_BASE_URL=http://72.56.99.214:4000/v1
LLM_CLOUD_API_KEY=sk-REPLACE_WITH_LITELLM_MASTER_KEY
LLM_CLOUD_MODEL=gpt-4.1-nano
ORCHESTRATION_ALLOW_FALLBACK=true
EOF
```

```bash
export LLM_TIER_DEFAULT=local
export ORCHESTRATION_ALLOW_FALLBACK=true
set -a; source .env; set +a

docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml -f docker-compose.ollama.yml --profile molt \
  up -d --build --force-recreate app

docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
  -f docker-compose.molt.yml -f docker-compose.ollama.yml --profile molt \
  exec app printenv LLM_TIER_DEFAULT LLM_LOCAL_BASE_URL LLM_CLOUD_BASE_URL ORCHESTRATION_ALLOW_FALLBACK
```

Smoke с RU к EU:

```bash
curl -sS -m 30 http://72.56.99.214:4000/health
curl -sS -m 60 http://72.56.99.214:4000/v1/chat/completions \
  -H "Authorization: Bearer $LLM_CLOUD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4.1-nano","messages":[{"role":"user","content":"ping"}],"max_tokens":8}'
```

---

## C) Проверка в Telegram

1. Обычный `#TASK …` → local (Ollama).  
2. `#TASK #CLOUD …` или кнопка **🧠 OpenAI (EU)** → cloud через LiteLLM.  
3. При сбое LLM и `ALLOW_FALLBACK=true` — rule-based (контур жив).

## Rollback

```bash
# RU: только local / fallback
sed -i 's/^LLM_TIER_DEFAULT=.*/LLM_TIER_DEFAULT=local/' .env
export LLM_TIER_DEFAULT=local ORCHESTRATION_ALLOW_FALLBACK=true
# recreate app …

# EU:
systemctl stop litellm
```
