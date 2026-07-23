# Протоколы storage и репозиториев. Конкретная реализация — адаптеры или shared_core.storage_impl.
from __future__ import annotations

from typing import Any, List, Optional, Protocol, runtime_checkable


# --- Generic entity types (минимальный контракт; детали в shared_schema) ---
class TaskRecord:
    pass


class RunRecord:
    pass


class DecisionRecord:
    pass


class ApprovalRecord:
    pass


class MemoryRecord:
    pass


class ArtifactRecord:
    pass


class EventRecord:
    pass


class ProjectRecord:
    pass


@runtime_checkable
class TaskRepository(Protocol):
    def get(self, task_id: str) -> Optional[TaskRecord]:
        ...

    def create(self, data: dict[str, Any]) -> TaskRecord:
        ...

    def update(self, task_id: str, data: dict[str, Any]) -> Optional[TaskRecord]:
        ...

    def list_by_project(self, project_id: str, filters: Optional[dict] = None) -> List[TaskRecord]:
        ...


@runtime_checkable
class RunRepository(Protocol):
    def get(self, run_id: str) -> Optional[RunRecord]:
        ...

    def create(self, data: dict[str, Any]) -> RunRecord:
        ...

    def update(self, run_id: str, data: dict[str, Any]) -> Optional[RunRecord]:
        ...

    def list_by_task(self, task_id: str) -> List[RunRecord]:
        ...


@runtime_checkable
class DecisionRepository(Protocol):
    def get(self, decision_id: str) -> Optional[DecisionRecord]:
        ...

    def create(self, data: dict[str, Any]) -> DecisionRecord:
        ...

    def list_by_task(self, task_id: str) -> List[DecisionRecord]:
        ...


@runtime_checkable
class ApprovalRepository(Protocol):
    def get(self, approval_id: str) -> Optional[ApprovalRecord]:
        ...

    def create(self, data: dict[str, Any]) -> ApprovalRecord:
        ...

    def update(self, approval_id: str, data: dict[str, Any]) -> Optional[ApprovalRecord]:
        ...

    def list_by_task(self, task_id: str) -> List[ApprovalRecord]:
        ...


@runtime_checkable
class MemoryRepository(Protocol):
    def get(self, project_id: str, scope: str, key: str) -> Optional[MemoryRecord]:
        ...

    def upsert(self, data: dict[str, Any]) -> MemoryRecord:
        ...

    def list_by_project(self, project_id: str, scope: Optional[str] = None) -> List[MemoryRecord]:
        ...


@runtime_checkable
class ArtifactRepository(Protocol):
    def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
        ...

    def create(self, data: dict[str, Any]) -> ArtifactRecord:
        ...

    def list_by_task(self, task_id: str) -> List[ArtifactRecord]:
        ...


@runtime_checkable
class EventRepository(Protocol):
    def append(self, data: dict[str, Any]) -> EventRecord:
        ...

    def list_by_run(self, run_id: str) -> List[EventRecord]:
        ...


@runtime_checkable
class ProjectRepository(Protocol):
    def get(self, project_id: str) -> Optional[ProjectRecord]:
        ...

    def create(self, data: dict[str, Any]) -> ProjectRecord:
        ...

    def update(self, project_id: str, data: dict[str, Any]) -> Optional[ProjectRecord]:
        ...


@runtime_checkable
class StorageProtocol(Protocol):
    """Единый контракт доступа к хранилищу. Адаптер реализует все репозитории."""

    @property
    def tasks(self) -> TaskRepository:
        ...

    @property
    def runs(self) -> RunRepository:
        ...

    @property
    def decisions(self) -> DecisionRepository:
        ...

    @property
    def approvals(self) -> ApprovalRepository:
        ...

    @property
    def memory(self) -> MemoryRepository:
        ...

    @property
    def artifacts(self) -> ArtifactRepository:
        ...

    @property
    def events(self) -> EventRepository:
        ...

    @property
    def projects(self) -> ProjectRepository:
        ...
