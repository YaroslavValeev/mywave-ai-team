# In-memory implementation of StorageProtocol for tests and smoke flow.
from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared_core.protocols import (
    ApprovalRecord,
    ArtifactRecord,
    DecisionRecord,
    EventRecord,
    MemoryRecord,
    ProjectRecord,
    RunRecord,
    TaskRecord,
)


def _record(data: dict[str, Any]) -> dict:
    """Record as dict; protocols accept dict-like access."""
    return dict(data)


class _InMemoryTaskRepo:
    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}

    def get(self, task_id: str) -> Optional[TaskRecord]:
        return _record(self._store[task_id]) if task_id in self._store else None

    def create(self, data: dict[str, Any]) -> TaskRecord:
        tid = data["task_id"]
        self._store[tid] = dict(data)
        return _record(self._store[tid])

    def update(self, task_id: str, data: dict[str, Any]) -> Optional[TaskRecord]:
        if task_id not in self._store:
            return None
        self._store[task_id].update(data)
        return _record(self._store[task_id])

    def list_by_project(self, project_id: str, filters: Optional[dict] = None) -> List[TaskRecord]:
        out = [v for v in self._store.values() if v.get("project_id") == project_id]
        return [_record(x) for x in out]


class _InMemoryRunRepo:
    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}

    def get(self, run_id: str) -> Optional[RunRecord]:
        return _record(self._store[run_id]) if run_id in self._store else None

    def create(self, data: dict[str, Any]) -> RunRecord:
        rid = data["run_id"]
        self._store[rid] = dict(data)
        return _record(self._store[rid])

    def update(self, run_id: str, data: dict[str, Any]) -> Optional[RunRecord]:
        if run_id not in self._store:
            return None
        self._store[run_id].update(data)
        return _record(self._store[run_id])

    def list_by_task(self, task_id: str) -> List[RunRecord]:
        out = [v for v in self._store.values() if v.get("task_id") == task_id]
        return [_record(x) for x in out]


class _InMemoryDecisionRepo:
    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}

    def get(self, decision_id: str) -> Optional[DecisionRecord]:
        return _record(self._store[decision_id]) if decision_id in self._store else None

    def create(self, data: dict[str, Any]) -> DecisionRecord:
        did = data["decision_id"]
        self._store[did] = dict(data)
        return _record(self._store[did])

    def list_by_task(self, task_id: str) -> List[DecisionRecord]:
        out = [v for v in self._store.values() if v.get("task_id") == task_id]
        return [_record(x) for x in out]


class _InMemoryApprovalRepo:
    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}

    def get(self, approval_id: str) -> Optional[ApprovalRecord]:
        return _record(self._store[approval_id]) if approval_id in self._store else None

    def create(self, data: dict[str, Any]) -> ApprovalRecord:
        aid = data["approval_id"]
        self._store[aid] = dict(data)
        return _record(self._store[aid])

    def update(self, approval_id: str, data: dict[str, Any]) -> Optional[ApprovalRecord]:
        if approval_id not in self._store:
            return None
        self._store[approval_id].update(data)
        return _record(self._store[approval_id])

    def list_by_task(self, task_id: str) -> List[ApprovalRecord]:
        out = [v for v in self._store.values() if v.get("task_id") == task_id]
        return [_record(x) for x in out]


class _InMemoryMemoryRepo:
    def __init__(self) -> None:
        self._store: Dict[tuple, dict] = {}  # (project_id, scope, key) -> row

    def get(self, project_id: str, scope: str, key: str) -> Optional[MemoryRecord]:
        k = (project_id, scope, key)
        return _record(self._store[k]) if k in self._store else None

    def upsert(self, data: dict[str, Any]) -> MemoryRecord:
        k = (data["project_id"], data["scope"], data["key"])
        self._store[k] = dict(data)
        return _record(self._store[k])

    def list_by_project(self, project_id: str, scope: Optional[str] = None) -> List[MemoryRecord]:
        out = [
            v for (pid, s, _), v in self._store.items()
            if pid == project_id and (scope is None or s == scope)
        ]
        return [_record(x) for x in out]


class _InMemoryArtifactRepo:
    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}

    def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
        return _record(self._store[artifact_id]) if artifact_id in self._store else None

    def create(self, data: dict[str, Any]) -> ArtifactRecord:
        aid = data["artifact_id"]
        self._store[aid] = dict(data)
        return _record(self._store[aid])

    def list_by_task(self, task_id: str) -> List[ArtifactRecord]:
        out = [v for v in self._store.values() if v.get("task_id") == task_id]
        return [_record(x) for x in out]


class _InMemoryEventRepo:
    def __init__(self) -> None:
        self._events: List[dict] = []

    def append(self, data: dict[str, Any]) -> EventRecord:
        self._events.append(dict(data))
        return _record(self._events[-1])

    def list_by_run(self, run_id: str) -> List[EventRecord]:
        out = [v for v in self._events if v.get("run_id") == run_id]
        return [_record(x) for x in out]


class _InMemoryProjectRepo:
    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}

    def get(self, project_id: str) -> Optional[ProjectRecord]:
        return _record(self._store[project_id]) if project_id in self._store else None

    def create(self, data: dict[str, Any]) -> ProjectRecord:
        pid = data["project_id"]
        self._store[pid] = dict(data)
        return _record(self._store[pid])

    def update(self, project_id: str, data: dict[str, Any]) -> Optional[ProjectRecord]:
        if project_id not in self._store:
            return None
        self._store[project_id].update(data)
        return _record(self._store[project_id])

    def list_all(self) -> List[ProjectRecord]:
        return [_record(v) for v in self._store.values()]


class InMemoryStorage:
    """Full in-memory implementation of StorageProtocol. For tests and smoke E2E."""

    def __init__(self) -> None:
        self._tasks = _InMemoryTaskRepo()
        self._runs = _InMemoryRunRepo()
        self._decisions = _InMemoryDecisionRepo()
        self._approvals = _InMemoryApprovalRepo()
        self._memory = _InMemoryMemoryRepo()
        self._artifacts = _InMemoryArtifactRepo()
        self._events = _InMemoryEventRepo()
        self._projects = _InMemoryProjectRepo()

    @property
    def tasks(self) -> _InMemoryTaskRepo:
        return self._tasks

    @property
    def runs(self) -> _InMemoryRunRepo:
        return self._runs

    @property
    def decisions(self) -> _InMemoryDecisionRepo:
        return self._decisions

    @property
    def approvals(self) -> _InMemoryApprovalRepo:
        return self._approvals

    @property
    def memory(self) -> _InMemoryMemoryRepo:
        return self._memory

    @property
    def artifacts(self) -> _InMemoryArtifactRepo:
        return self._artifacts

    @property
    def events(self) -> _InMemoryEventRepo:
        return self._events

    @property
    def projects(self) -> _InMemoryProjectRepo:
        return self._projects
