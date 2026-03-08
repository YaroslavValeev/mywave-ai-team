# Security — MyWave AI-TEAM

## Секреты

- `.env`, `.env.local` в `.gitignore`, не коммитить.
- Токены, ключи, пароли — только в переменных окружения.
- Redaction по умолчанию для PII/токенов (Telegram, Dashboard, reports, logs).
- В артефактах/логах/DEV_REPORT — никогда env-значений и токенов.

## GH_TOKEN (v0.2.1)

- **Хранение:** только локально на машине Owner/Runner (например в `.env.local`).
- **На сервер GH_TOKEN не попадает.** Runner работает локально, сервер не знает GitHub token.
- **Merge:** любые merge-операции запрещены runner'ом. Только Owner вручную в GitHub UI.
- **CI:** token leakage scan проверяет репо на паттерны `ghp_`, `github_pat_`, `sk-`, `xoxb-`, `-----BEGIN` — при совпадении CI падает.

## Auth

- Dashboard: OWNER_API_KEY (X-API-Key) обязателен, fail-fast при старте без ключа.
- Production: Caddy BasicAuth + X-API-Key (dual layer).
- Внешние вызовы только через HTTPS API + OWNER_API_KEY.

## CRITICAL_EXECUTE

Флаги: prod_deploy, public_publish, money_or_pricing, pii_or_sensitive, legal_commitment.  
При любом true — WAIT_OWNER, Approve через Telegram кнопки.
