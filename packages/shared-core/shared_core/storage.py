# Единый протокол Storage: точка доступа ко всем репозиториям.
# Конкретная реализация (SQLite, PostgreSQL, in-memory) реализует StorageProtocol.
from __future__ import annotations

from shared_core.protocols import (
    StorageProtocol,
    TaskRepository,
    RunRepository,
    DecisionRepository,
    ApprovalRepository,
    MemoryRepository,
    ArtifactRepository,
    EventRepository,
    ProjectRepository,
)

__all__ = [
    "StorageProtocol",
    "TaskRepository",
    "RunRepository",
    "DecisionRepository",
    "ApprovalRepository",
    "MemoryRepository",
    "ArtifactRepository",
    "EventRepository",
    "ProjectRepository",
]
