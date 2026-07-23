# Реестр сущностей по id (опциональный слой разрешения).
# Позволяет единой точкой получать тип сущности по id без обращения ко всем репозиториям.
from __future__ import annotations

from typing import Optional

# Заглушка: при подключении Storage реестр может кэшировать task_id -> "task", run_id -> "run" и т.д.
# Используется для валидации и маршрутизации.


def entity_type_from_id(entity_id: str) -> Optional[str]:
    """По префиксу id возвращает тип сущности: task, run, decision, approval, artifact, memory, event, project."""
    if not entity_id or "_" not in entity_id:
        return None
    prefix = entity_id.split("_", 1)[0].lower()
    mapping = {
        "task": "task",
        "run": "run",
        "dec": "decision",
        "appr": "approval",
        "art": "artifact",
        "mem": "memory",
        "evt": "event",
        "proj": "project",
    }
    return mapping.get(prefix)
