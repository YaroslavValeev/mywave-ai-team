# STORE_AND_BACKUP_READINESS_MODEL — Готовность хранилищ и бэкапов

## Критичные stores

| Store | Проверка |
|-------|----------|
| main_db | Session + простой query (например count tasks) не падает |
| registry_yaml | domain_registry, specializations, routing, policy — YAML читаемы и валидны |
| registry_backup_dir | app/data/backups (или REGISTRY_BACKUPS_DIR) существует, writable |

## Backup assumptions

- **Postgres:** scripts/backup_postgres.sh, scripts/restore_postgres.sh (см. RUNBOOK).
- **Registry:** snapshot перед patch apply (registry_backups.create_snapshot).

## Rollback paths

- Registry patch: restore_from_backup(backup_ref, target_file).
- Postgres: restore_postgres.sh (вне приложения).
