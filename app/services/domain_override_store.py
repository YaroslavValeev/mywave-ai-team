# app/services/domain_override_store.py — Phase 10.1: persist owner override for task primary domain
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_OVERRIDES_PATH = Path(__file__).resolve().parents[1] / "data" / "domain_overrides.json"
_LOCK = None


def _load_overrides() -> dict[str, Any]:
    """Загрузить все overrides из JSON файла."""
    if not _OVERRIDES_PATH.parent.exists():
        _OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _OVERRIDES_PATH.exists():
        return {}
    try:
        with open(_OVERRIDES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_overrides(data: dict[str, Any]) -> None:
    with open(_OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)


def get_override(task_id: int) -> Optional[dict[str, Any]]:
    """Получить активный override для задачи."""
    key = str(task_id)
    data = _load_overrides()
    rec = data.get(key)
    if not rec or not rec.get("override_active", True):
        return None
    return rec


def set_override(
    task_id: int,
    new_primary_domain: str,
    reason: Optional[str] = None,
    actor: str = "owner",
    source: str = "telegram",
    previous_primary_domain: Optional[str] = None,
) -> dict[str, Any]:
    """Установить override для задачи. Возвращает запись."""
    key = str(task_id)
    data = _load_overrides()
    now = datetime.now(timezone.utc).isoformat()
    rec = {
        "task_id": task_id,
        "new_primary_domain": new_primary_domain,
        "previous_primary_domain": previous_primary_domain,
        "override_reason": reason or "",
        "override_actor": actor,
        "override_source": source,
        "override_timestamp": now,
        "override_active": True,
    }
    data[key] = rec
    _save_overrides(data)
    return rec


def clear_override(task_id: int) -> bool:
    """Снять override (деактивировать). Возвращает True если был активен."""
    key = str(task_id)
    data = _load_overrides()
    if key not in data:
        return False
    data[key]["override_active"] = False
    _save_overrides(data)
    return True
