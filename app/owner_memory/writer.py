# Запись inferred-паттернов (tier=inferred, без auto-apply как hard rule)
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from app.shared.audit import log_audit

if TYPE_CHECKING:
    from app.storage.repositories import TaskRepository

logger = logging.getLogger(__name__)


def write_inferred_pattern(
    repo: TaskRepository,
    *,
    owner_key: str = "default",
    item_key: str,
    text: str,
    scope: str = "global",
) -> None:
    """Сохраняет паттерн как inferred; движок не применяет без is_confirmed=True."""
    if os.getenv("OWNER_MEMORY_INFERRED_WRITE", "false").strip().lower() not in {"1", "true", "yes"}:
        logger.info("OWNER_MEMORY_INFERRED_WRITE off; skip inferred pattern %s", item_key)
        return
    try:
        repo.add_owner_memory_item(
            owner_key=owner_key,
            kind="pattern",
            item_key=item_key,
            text=text[:4000],
            tier="inferred",
            scope=scope,
            strength=0.4,
            weight=0.4,
            priority_rank=70,
            is_active=True,
            is_confirmed=False,
            meta_json={"source": "inferred_stub"},
        )
        log_audit(
            repo,
            "owner_pattern_inferred_stored",
            payload={"item_key": item_key, "owner_key": owner_key, "scope": scope},
        )
    except Exception as exc:
        logger.warning("write_inferred_pattern failed: %s", exc)
