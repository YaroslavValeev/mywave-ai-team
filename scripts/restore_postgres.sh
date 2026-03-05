#!/usr/bin/env bash
# restore_postgres.sh — восстановление из backup
# Использование: ./scripts/restore_postgres.sh /path/to/backup.sql.gz
# ВНИМАНИЕ: перезаписывает текущую БД!

set -e

BACKUP_FILE="${1:?Usage: $0 /path/to/backup.sql.gz}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-.}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "File not found: $BACKUP_FILE"
  exit 1
fi

cd "$COMPOSE_PROJECT_DIR"

echo "Restoring from $BACKUP_FILE..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
  zcat "$BACKUP_FILE" | docker compose exec -T postgres psql -U mywave -d mywave_ai
else
  docker compose exec -T postgres psql -U mywave -d mywave_ai < "$BACKUP_FILE"
fi
echo "Restore complete. Restart app: docker compose restart app"
