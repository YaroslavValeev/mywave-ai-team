# Proposal – patch – apply relation (Phase 10.7)

Связь Phase 10.6 и 10.7.

- **Proposal** — refinement proposal (accepted) из Phase 10.6; источник для построения патча.
- **Patch candidate** — результат build_patch_candidate: target_file, patch_type, proposed mutation, diff_summary, risk (safe/unsafe).
- **Dry-run** — выполнение логики apply в памяти и возврат diff и preview без записи в файлы; нужно для показа owner перед реальным apply.
- **Validation** — проверка структуры и дубликатов по «новому» содержимому; без ok apply не выполняется.
- **Apply** — запись в target_file для safe patch types; создание backup до записи; обновление proposal status=applied; запись audit registry_patch_applied.
- **Backup** — снимок файла до apply; backup_ref хранится в метаданных и audit.
- **Rollback** — восстановление файла из backup; только для safe types с rollback_supported.
- **Audit** — все перечисленные шаги (built, dry_run, validated, applied, rollback, failed) логируются в audit_events.

Итог: accepted proposal → build patch → dry-run (опционально, но рекомендуется) → validate → backup → apply → audit; при необходимости rollback по backup_ref.
