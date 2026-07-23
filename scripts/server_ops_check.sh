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

MOLT_ACTIVE=false
if ss -lntp 2>/dev/null | grep -q ':8765'; then
  MOLT_ACTIVE=true
fi
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qE 'ai-team-molt|-molt-'; then
  MOLT_ACTIVE=true
fi

COMPOSE_PROFILE=()
if [[ "$MOLT_ACTIVE" == true ]] && [[ -f docker-compose.molt.yml ]]; then
  COMPOSE+=(-f docker-compose.molt.yml)
  COMPOSE_PROFILE=(--profile molt)
fi

echo "=== compose ==="
"${COMPOSE[@]}" "${COMPOSE_PROFILE[@]}" ps
echo

echo "=== disk ==="
ROOT_USE="$(df -P / 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
if [[ -n "${ROOT_USE:-}" ]]; then
  if (( ROOT_USE >= 85 )); then
    echo "FAIL disk root ${ROOT_USE}% used (>=85%)"
  elif (( ROOT_USE >= 70 )); then
    echo "WARN disk root ${ROOT_USE}% used (>=70%) — hint: bash scripts/server_disk_cleanup.sh"
  else
    echo "OK disk root ${ROOT_USE}% used"
  fi
fi
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

echo "=== molt :8765 ==="
if ss -lntp 2>/dev/null | grep -q ':8765'; then
  echo "ON: порт 8765 слушается (Molt profile активен)"
  ss -lntp 2>/dev/null | grep ':8765' || true
  curl -sS -m 5 http://127.0.0.1:8765/health 2>/dev/null || echo "FAIL molt /health"
  echo
  ready_body="$(curl -sS -m 5 http://127.0.0.1:8765/ready 2>/dev/null || true)"
  if [[ -n "$ready_body" ]]; then
    echo "$ready_body"
    if echo "$ready_body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ready"'; then
      if [[ -f scripts/molt/smoke_check_molt_http.py ]]; then
        MOLT_HTTP_BASE_URL=http://127.0.0.1:8765 python3 scripts/molt/smoke_check_molt_http.py || true
      else
        exec_body="$(curl -sS -m 5 -X POST http://127.0.0.1:8765/executions \
          -H 'Content-Type: application/json' \
          -d '{"canonical_task_id":"smoke-check-dummy-task"}' 2>/dev/null || true)"
        if echo "$exec_body" | grep -q '"accepted"'; then
          echo "smoke POST /executions ok: $exec_body"
        else
          echo "WARN molt POST /executions: ${exec_body:-no response}"
        fi
      fi
    fi
  else
    echo "FAIL molt /ready"
  fi
else
  echo "OK: Molt не слушает 8765 (норма без --profile molt)"
fi
echo

echo "=== docker images (ai-team) ==="
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' | head -20
echo
echo "OK: ops check finished"
