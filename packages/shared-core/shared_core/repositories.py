# Интерфейсы репозиториев (алиасы к protocols для обратной совместимости и явного места).
from shared_core.protocols import (
    TaskRepository as TaskRepositoryProtocol,
    RunRepository as RunRepositoryProtocol,
    DecisionRepository as DecisionRepositoryProtocol,
    ApprovalRepository as ApprovalRepositoryProtocol,
    MemoryRepository as MemoryRepositoryProtocol,
    ArtifactRepository as ArtifactRepositoryProtocol,
    EventRepository as EventRepositoryProtocol,
)

__all__ = [
    "TaskRepositoryProtocol",
    "RunRepositoryProtocol",
    "DecisionRepositoryProtocol",
    "ApprovalRepositoryProtocol",
    "MemoryRepositoryProtocol",
    "ArtifactRepositoryProtocol",
    "EventRepositoryProtocol",
]
