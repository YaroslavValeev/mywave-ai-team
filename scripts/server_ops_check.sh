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

# After --build, alembic/app may need ~30–90s; avoid false 502/reset.
wait_health() {
  local label="$1"
  local url="$2"
  local timeout_sec="${3:-90}"
  local deadline=$((SECONDS + timeout_sec))
  local body=""
  local attempt=0
  while (( SECONDS < deadline )); do
    attempt=$((attempt + 1))
    body="$(curl -sS -m 5 -H "X-API-Key: ${OWNER_API_KEY}" "$url" 2>/dev/null || true)"
    if echo "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      echo "$body"
      return 0
    fi
    sleep 3
  done
  echo "FAIL ${label} after ${timeout_sec}s (${attempt} attempts)"
  if [[ -n "$body" ]]; then
    echo "$body"
  fi
  return 1
}

echo "=== local health :8088 (wait up to 90s) ==="
wait_health "local" "http://127.0.0.1:8088/api/system/health" 90 || true
echo
echo

echo "=== public health ${BASE_URL} (wait up to 60s) ==="
wait_health "public" "${BASE_URL}/api/system/health" 60 || true
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

echo "=== molt :8765 (expect OFF on RU) ==="
if ss -lntp 2>/dev/null | grep -q ':8765'; then
  echo "WARN: порт 8765 слушается — Molt profile может быть включён (см. docker-compose.molt.yml)"
  ss -lntp 2>/dev/null | grep ':8765' || true
else
  echo "OK: Molt не слушает 8765 (норма без Owner GO / --profile molt)"
fi
echo

echo "=== docker images (ai-team) ==="
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' | head -20
echo
echo "OK: ops check finished"
