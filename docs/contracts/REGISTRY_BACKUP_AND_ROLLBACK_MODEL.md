# Registry backup and rollback model (Phase 10.7)

## Backup

- **Когда:** перед применением патча к registry-файлу (перед записью в target_file).
- **Где хранить:** каталог app/data/backups/ (или заданный через REGISTRY_BACKUPS_DIR); имя файла например specializations_20260317_143022.yaml (timestamp).
- **Содержимое:** полная копия содержимого целевого файла на момент до apply.
- **backup_ref** — путь к backup-файлу или уникальный идентификатор; сохраняется в метаданных патча и в audit payload (registry_patch_applied).

## Связь с patch/apply audit

- В событии registry_patch_applied в payload передаётся proposal_id, target_file, backup_ref, patch_type.
- По backup_ref при необходимости можно выполнить rollback.

## Rollback

- **Условие:** только для патчей с rollback_supported=true (safe append/add); откат = перезапись target_file содержимым из backup_ref.
- **Действие:** прочитать backup_ref, записать в target_file; зафиксировать в audit registry_patch_rollback.
- **Ограничение:** не строить сложную version-control платформу; один backup на apply; при повторном apply того же файла предыдущий backup может быть перезаписан или храниться отдельно (реализация — минимально достаточная).
