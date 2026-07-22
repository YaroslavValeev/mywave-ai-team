#!/usr/bin/env bash
# install_backup_cron.sh — ежедневный pg_dump для AI-TEAM на RU-сервере
# Usage (as root, from /opt/mywave/ai-team):
#   bash scripts/install_backup_cron.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/mywave/ai-team}"
BACKUP_DIR="${BACKUP_DIR:-/opt/mywave/backups/ai-team}"
CRON_LINE="0 3 * * * COMPOSE_PROJECT_DIR=${APP_DIR} COMPOSE_FILE=docker-compose.yml:docker-compose.server.yml ${APP_DIR}/scripts/backup_postgres.sh ${BACKUP_DIR} >> /var/log/mywave-ai-team-backup.log 2>&1"

mkdir -p "$BACKUP_DIR"
chmod +x "${APP_DIR}/scripts/backup_postgres.sh" || true

# Compose v2: backup script uses `docker compose` — ensure PROJECT dir has compose files
if [[ ! -f "${APP_DIR}/docker-compose.yml" ]]; then
  echo "ERROR: ${APP_DIR}/docker-compose.yml not found"
  exit 1
fi

# Install/replace cron entry
TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v 'backup_postgres.sh' > "$TMP" || true
echo "$CRON_LINE" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Installed cron:"
echo "  $CRON_LINE"
echo "Backup dir: $BACKUP_DIR"
echo "Test now:"
echo "  COMPOSE_PROJECT_DIR=${APP_DIR} ${APP_DIR}/scripts/backup_postgres.sh ${BACKUP_DIR}"
