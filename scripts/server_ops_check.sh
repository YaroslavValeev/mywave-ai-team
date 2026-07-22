#!/usr/bin/env bash
# server_ops_check.sh — быстрая проверка AI-TEAM на RU (office-lite / office-full)
# Usage (from /opt/mywave/ai-team, root):
#   bash scripts/server_ops_check.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/mywave/ai-team}"
BACKUP_DIR="${BACKUP_DIR:-/opt/mywave/backups/ai-team}"
cd "$APP_DIR"

# shellcheck disable=SC1091
set -a
# shellcheck source=/dev/null
source .env 2>/dev/null || true
set +a

OWNER_API_KEY="${OWNER_API_KEY:-}"
BASE_URL="${DASHBOARD_URL:-https://agm.mywavewake.ru}"

# Prefer full overlay if present in running stack hint
COMPOSE=(docker compose -f docker-compose.yml)
if docker compose -f docker-compose.yml -f docker-compose.server-full.yml ps --status running 2>/dev/null | grep -q app; then
  COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.server-full.yml)
elif [[ -f docker-compose.server.yml ]]; then
  COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.server.yml)
fi

echo "=== compose ==="
"${COMPOSE[@]}" ps
echo

echo "=== disk ==="
df -h / /var/lib/docker 2>/dev/null | head -20 || df -h /
echo

echo "=== local health :8088 ==="
curl -sS -m 10 -H "X-API-Key: ${OWNER_API_KEY}" "http://127.0.0.1:8088/api/system/health" || echo "FAIL local"
echo
echo

echo "=== public health ${BASE_URL} ==="
curl -sS -m 15 -H "X-API-Key: ${OWNER_API_KEY}" "${BASE_URL}/api/system/health" || echo "FAIL public"
echo
echo

echo "=== nginx agm ==="
nginx -t 2>&1 | tail -5 || true
systemctl is-active nginx || true
echo

echo "=== backup cron ==="
crontab -l 2>/dev/null | grep -E 'backup_postgres|mywave-ai-team' || echo "NO backup cron line"
ls -la "${BACKUP_DIR}" 2>/dev/null | tail -10 || echo "NO backup dir yet"
echo

echo "=== docker images (ai-team) ==="
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' | head -20
echo
echo "OK: ops check finished"
