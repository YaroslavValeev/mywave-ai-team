#!/usr/bin/env bash
# Deploy AI-TEAM (agm) на RU-сервер mywave-bot-server (62.113.42.227).
# Запускать ПОСЛЕ копирования кода и заполнения .env:
#   bash scripts/deploy_agm_on_server.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/mywave/ai-team}"
cd "$APP_DIR"

echo "==> Working dir: $APP_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: .env missing. Copy from .env.example and fill secrets first."
  exit 1
fi

if [[ ! -f Caddyfile ]]; then
  echo "ERROR: Caddyfile missing. cp Caddyfile.example Caddyfile and insert BasicAuth hash."
  exit 1
fi

# Порты HTTPS
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 80/tcp || true
  sudo ufw allow 443/tcp || true
fi

echo "==> Build & start (office-lite default; set DOCKER_BUILD_TARGET=full for CrewAI)"
docker compose up -d --build

echo "==> Status"
docker compose ps

echo "==> Tail app logs (Ctrl+C to stop watching)"
docker compose logs --tail=80 app
