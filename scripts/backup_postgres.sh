#!/usr/bin/env bash
# backup_postgres.sh — daily backup Postgres (retention 7 daily + 4 weekly)
# Использование: ./scripts/backup_postgres.sh [BACKUP_DIR]
# Cron: 0 3 * * * /path/to/scripts/backup_postgres.sh /backups

set -e

BACKUP_DIR="${1:-./backups}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-.}"
RETENTION_DAYS=7
RETENTION_WEEKS=4

mkdir -p "$BACKUP_DIR"
cd "$COMPOSE_PROJECT_DIR"

DATE=$(date +%Y%m%d)
WEEKDAY=$(date +%u)
DAILY_FILE="$BACKUP_DIR/mywave_ai_${DATE}_daily.sql.gz"
WEEKLY_FILE="$BACKUP_DIR/mywave_ai_${DATE}_weekly.sql.gz"

# Daily backup (--clean for restore into existing DB)
docker compose exec -T postgres pg_dump -U mywave mywave_ai --clean --if-exists | gzip > "$DAILY_FILE"
echo "Backup: $DAILY_FILE"

# Weekly backup (воскресенье)
if [ "$WEEKDAY" -eq 7 ]; then
  cp "$DAILY_FILE" "$WEEKLY_FILE"
  echo "Weekly backup: $WEEKLY_FILE"
fi

# Ротация: удалить daily старше RETENTION_DAYS
find "$BACKUP_DIR" -name "mywave_ai_*_daily.sql.gz" -mtime +$RETENTION_DAYS -delete

# Ротация: оставить только RETENTION_WEEKS последних weekly
ls -t "$BACKUP_DIR"/mywave_ai_*_weekly.sql.gz 2>/dev/null | tail -n +$((RETENTION_WEEKS + 1)) | xargs -r rm
echo "Rotation done (daily: ${RETENTION_DAYS}d, weekly: ${RETENTION_WEEKS})"
