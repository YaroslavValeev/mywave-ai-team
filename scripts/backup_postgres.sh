#!/usr/bin/env bash
# backup_postgres.sh — daily backup Postgres (retention 30 days, Variant A)
# OWNER-DECISIONS: retention_days=30 (минимум 7 по SLA)
# Использование: ./scripts/backup_postgres.sh [BACKUP_DIR]
# Cron: 0 3 * * * /path/to/scripts/backup_postgres.sh /backups

set -e

BACKUP_DIR="${1:-./backups}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-.}"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"
cd "$COMPOSE_PROJECT_DIR"

DATE=$(date +%Y%m%d)
DAILY_FILE="$BACKUP_DIR/mywave_ai_${DATE}.sql.gz"

# Daily backup (--clean for restore into existing DB)
docker compose exec -T postgres pg_dump -U mywave mywave_ai --clean --if-exists | gzip > "$DAILY_FILE"
echo "Backup: $DAILY_FILE"

# Ротация: удалить daily старше RETENTION_DAYS
find "$BACKUP_DIR" -name "mywave_ai_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "Rotation done (retention: ${RETENTION_DAYS} days)"
