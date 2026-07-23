# Контракт доступа к проектной памяти (MemoryEntry).
# Владелец — shared-core; любой слой читает/пишет через MemoryRepository.
from __future__ import annotations

from typing import Any, List, Optional

from shared_core.protocols import MemoryRepository, MemoryRecord


# Контракт использования (для документирования и тестов):
# - get(project_id, scope, key) -> MemoryRecord | None
# - upsert(data) -> MemoryRecord; data содержит project_id, scope, key, value, updated_at и опционально memory_id, source, confidence, ttl, linked_task_id, linked_artifact_id
# - list_by_project(project_id, scope?) -> List[MemoryRecord]
#
# memory_id при создании выдаёт MemoryIdFactory (shared_core.ids).


def memory_contract_required_fields() -> List[str]:
    """Обязательные поля для upsert MemoryEntry (без memory_id — его выдаёт core)."""
    return ["project_id", "scope", "key", "value", "updated_at"]
