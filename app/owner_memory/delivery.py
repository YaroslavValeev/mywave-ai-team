# Мягкое влияние preferences на короткие owner-facing ответы (v1-minimal)
from __future__ import annotations

from app.owner_memory.service import OwnerMemoryService, owner_memory_enabled
from app.storage.repositories import TaskRepository


def format_owner_delivery_note(repo: TaskRepository, *, owner_key: str = "default") -> str:
    if not owner_memory_enabled():
        return ""
    svc = OwnerMemoryService(repo, owner_key)
    bundle = svc.build_owner_rules_bundle(context_scopes=["delivery", "global"])
    if not bundle.preferences:
        return ""
    keys = [p.item_key for p in bundle.preferences[:4]]
    return "\n—\nКонтур владельца (предпочтения): " + ", ".join(keys)
