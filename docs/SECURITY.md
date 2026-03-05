# Security — MyWave AI-TEAM

## Секреты

- `.env` в `.gitignore`, не коммитить.
- Токены, ключи, пароли — только в переменных окружения.
- Redaction по умолчанию для PII/токенов (Telegram, Dashboard, reports, logs).

## Auth

- Dashboard: OWNER_API_KEY (X-API-Key) обязателен, fail-fast при старте без ключа.
- Production: Caddy BasicAuth + X-API-Key (dual layer).

## CRITICAL_EXECUTE

Флаги: prod_deploy, public_publish, money_or_pricing, pii_or_sensitive, legal_commitment.  
При любом true — WAIT_OWNER, Approve через Telegram кнопки.
