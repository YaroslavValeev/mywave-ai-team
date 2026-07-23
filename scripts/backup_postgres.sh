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
# На RU: COMPOSE_FILE=docker-compose.yml:docker-compose.server.yml
COMPOSE_ARGS=()
if [[ -n "${COMPOSE_FILE:-}" ]]; then
  IFS=':' read -ra _cf <<< "$COMPOSE_FILE"
  for f in "${_cf[@]}"; do
    COMPOSE_ARGS+=(-f "$f")
  done
elif [[ -f docker-compose.server.yml ]]; then
  COMPOSE_ARGS=(-f docker-compose.yml -f docker-compose.server.yml)
fi

docker compose "${COMPOSE_ARGS[@]}" exec -T postgres pg_dump -U mywave mywave_ai --clean --if-exists | gzip > "$DAILY_FILE"
echo "Backup: $DAILY_FILE"

# Molt canonical.db (optional — не ломаем pg backup при отсутствии volume)
MOLT_VOLUME=""
if docker volume ls --format '{{.Name}}' 2>/dev/null | grep -q 'molt_data'; then
  MOLT_VOLUME="$(docker volume ls --format '{{.Name}}' 2>/dev/null | grep 'molt_data' | head -1)"
fi

HAS_MOLT_COMPOSE=false
if [[ -f docker-compose.molt.yml ]]; then
  HAS_MOLT_COMPOSE=true
fi
if echo "${COMPOSE_FILE:-}" | grep -q 'docker-compose.molt.yml'; then
  HAS_MOLT_COMPOSE=true
fi

if [[ -z "$MOLT_VOLUME" ]] && [[ "$HAS_MOLT_COMPOSE" == true ]]; then
  _molt_vols=()
  if [[ -f docker-compose.molt.yml ]]; then
    _molt_compose=(-f docker-compose.yml -f docker-compose.molt.yml)
    if [[ ${#COMPOSE_ARGS[@]} -gt 0 ]]; then
      _molt_compose=("${COMPOSE_ARGS[@]}" -f docker-compose.molt.yml)
    fi
    mapfile -t _molt_vols < <(docker compose "${_molt_compose[@]}" config --volumes 2>/dev/null | grep -E 'molt_data' || true)
  fi
  if [[ ${#_molt_vols[@]} -gt 0 ]]; then
    _proj="$(docker compose "${COMPOSE_ARGS[@]}" config --format json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('name',''))" 2>/dev/null || true)"
    if [[ -n "$_proj" ]]; then
      _candidate="${_proj}_molt_data"
      if docker volume inspect "$_candidate" >/dev/null 2>&1; then
        MOLT_VOLUME="$_candidate"
      fi
    fi
  fi
fi

if [[ -n "$MOLT_VOLUME" ]] || [[ "$HAS_MOLT_COMPOSE" == true ]]; then
  CANONICAL_OUT="$BACKUP_DIR/canonical_${DATE}.db"
  if [[ -n "$MOLT_VOLUME" ]]; then
    if docker run --rm -v "${MOLT_VOLUME}:/data:ro" -v "${BACKUP_DIR}:/out" alpine cp /data/canonical.db "/out/canonical_${DATE}.db" 2>/dev/null; then
      echo "Backup: $CANONICAL_OUT (from volume ${MOLT_VOLUME})"
    else
      echo "WARN: molt canonical.db backup skipped (file missing in ${MOLT_VOLUME})"
    fi
  else
    echo "WARN: molt_data volume not found; skipping canonical.db backup"
  fi
fi

# Ротация: удалить daily старше RETENTION_DAYS
find "$BACKUP_DIR" -name "mywave_ai_*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "canonical_*.db" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "canonical_*.db.gz" -mtime +$RETENTION_DAYS -delete
echo "Rotation done (retention: ${RETENTION_DAYS} days)"
