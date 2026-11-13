# app/services/registry_backups.py — Phase 10.7: backup/snapshot before patch apply
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

_BASE = Path(__file__).resolve().parents[1]
_DEFAULT_BACKUP_DIR = _BASE / "data" / "backups"


def get_backup_dir() -> Path:
    path = os.environ.get("REGISTRY_BACKUPS_DIR", str(_DEFAULT_BACKUP_DIR))
    return Path(path)


def create_snapshot(target_file: Path) -> tuple[Optional[str], Optional[str]]:
    """
    Создать снимок файла до apply.
    Возвращает (backup_ref, error). backup_ref — путь к backup-файлу или идентификатор.
    """
    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    if not target_file.exists():
        return None, "target file does not exist"
    try:
        content = target_file.read_text(encoding="utf-8")
    except Exception as e:
        return None, str(e)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    name = target_file.stem + "_" + stamp + target_file.suffix
    backup_path = backup_dir / name
    try:
        backup_path.write_text(content, encoding="utf-8")
        return str(backup_path), None
    except Exception as e:
        return None, str(e)


def restore_from_backup(backup_ref: str, target_file: Path) -> Optional[str]:
    """
    Восстановить target_file из backup_ref (rollback).
    Возвращает None при успехе, иначе строку ошибки.
    """
    path = Path(backup_ref)
    if not path.exists():
        return f"backup not found: {backup_ref}"
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return str(e)
    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
        return None
    except Exception as e:
        return str(e)
