"""Загрузка канона из YAML (тесты и окружения без alembic upgrade)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from app.storage.repositories import TaskRepository


def canon_yaml_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "owner_memory_canon.yaml"


def ensure_canonical_owner_memory(repo: TaskRepository, owner_key: str | None = None) -> None:
    """Идемпотентный seed профиля и items из owner_memory_canon.yaml."""
    path = canon_yaml_path()
    if not path.is_file():
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    profile = data.get("profile") or {}
    ok = owner_key or profile.get("owner_key") or "default"
    if repo.get_owner_profile(ok) and repo.count_owner_memory_items(ok) >= 5:
        return
    now = datetime.utcnow()
    if not repo.get_owner_profile(ok):
        from app.storage.models import OwnerProfile

        p = OwnerProfile(
            owner_key=ok,
            display_name=profile.get("display_name") or "Owner",
            role=profile.get("role"),
            primary_interface=profile.get("primary_interface"),
            preferred_work_mode=profile.get("preferred_work_mode"),
            created_at=now,
            updated_at=now,
        )
        repo.session.add(p)
        repo.session.commit()

    existing_keys = {
        row.item_key
        for row in repo.list_owner_memory_items(ok, active_only=False, scopes=None)
    }
    for item in data.get("items") or []:
        ik = item.get("item_key")
        if not ik or ik in existing_keys:
            continue
        repo.add_owner_memory_item(
            owner_key=ok,
            kind=item.get("kind") or "rule",
            item_key=ik,
            text=item.get("text") or "",
            tier=item.get("tier") or "canonical",
            scope=item.get("scope") or "global",
            strength=float(item.get("strength") or 1.0),
            weight=float(item.get("weight") or item.get("strength") or 1.0),
            priority_rank=int(item.get("priority_rank") or 0),
            is_active=bool(item.get("is_active", True)),
            is_confirmed=bool(item.get("is_confirmed", True)),
            meta_json=None,
        )
        existing_keys.add(ik)
