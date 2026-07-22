#!/usr/bin/env bash
# restore_postgres.sh — восстановление из backup
# Использование: ./scripts/restore_postgres.sh /path/to/backup.sql.gz
# ВНИМАНИЕ: перезаписывает текущую БД!
#
# На RU (office-full):
#   COMPOSE_PROJECT_DIR=/opt/mywave/ai-team \
#   COMPOSE_FILE=docker-compose.yml:docker-compose.server-full.yml \
#   ./scripts/restore_postgres.sh /opt/mywave/backups/ai-team/mywave_ai_YYYYMMDD.sql.gz

set -euo pipefail

BACKUP_FILE="${1:?Usage: $0 /path/to/backup.sql.gz}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-.}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "File not found: $BACKUP_FILE"
  exit 1
fi

cd "$COMPOSE_PROJECT_DIR"

COMPOSE_ARGS=()
if [[ -n "${COMPOSE_FILE:-}" ]]; then
  IFS=':' read -ra _cf <<< "$COMPOSE_FILE"
  for f in "${_cf[@]}"; do
    COMPOSE_ARGS+=(-f "$f")
  done
elif [[ -f docker-compose.server-full.yml ]] && docker compose -f docker-compose.yml -f docker-compose.server-full.yml ps --status running 2>/dev/null | grep -q postgres; then
  COMPOSE_ARGS=(-f docker-compose.yml -f docker-compose.server-full.yml)
elif [[ -f docker-compose.server.yml ]]; then
  COMPOSE_ARGS=(-f docker-compose.yml -f docker-compose.server.yml)
fi

echo "Restoring from $BACKUP_FILE..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
  zcat "$BACKUP_FILE" | docker compose "${COMPOSE_ARGS[@]}" exec -T postgres psql -U mywave -d mywave_ai
else
  docker compose "${COMPOSE_ARGS[@]}" exec -T postgres psql -U mywave -d mywave_ai < "$BACKUP_FILE"
fi
echo "Restore complete. Restart app:"
echo "  docker compose ${COMPOSE_ARGS[*]} restart app"
