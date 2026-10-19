"""Deny-by-default scoped repository. Not an authentication mechanism.

The caller must supply an authenticated principal, never a model-provided actor.
No new HTTP/agent intake uses this repository until all integration guards exist.
"""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from sqlalchemy import or_, select

from app.storage.models import (
    AuditEvent,
    MemoryEntry,
    Project,
    ProjectAccessGrant,
    Task,
    Workspace,
    WorkspaceMembership,
)


class ScopeDenied(PermissionError):
    """No existence or record content is disclosed in the error."""


@dataclass(frozen=True)
class Scope:
    principal_id: str
    workspace_id: int
    project_id: int

    def __post_init__(self):
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ScopeDenied("Scoped access denied")
        if any(
            type(value) is not int or value <= 0
            for value in (self.workspace_id, self.project_id)
        ):
            raise ScopeDenied("Scoped access denied")


@dataclass(frozen=True)
class TaskView:
    id: int
    workspace_id: int
    project_id: int
    status: str
    owner_text: str


@dataclass(frozen=True)
class MemoryView:
    id: int
    workspace_id: int
    project_id: int
    content: str
    source_ref: str | None


class ScopedRepository:
    def __init__(self, session, scope: Scope):
        self.session = session
        self.scope = scope

    def _one(self, query):
        # Do not reuse an identity-map copy of a grant after a concurrent revocation.
        return self.session.scalar(query.execution_options(populate_existing=True))

    def _authorize(self, action):
        if action not in {"read", "write"}:
            raise ScopeDenied("Scoped access denied")
        s = self.scope

        def fetch(query):
            # PostgreSQL serializes a permission-changing update against this write.
            return self._one(query.with_for_update() if action == "write" else query)

        workspace = fetch(select(Workspace).where(Workspace.id == s.workspace_id))
        project = fetch(
            select(Project).where(
                Project.id == s.project_id, Project.workspace_id == s.workspace_id
            )
        )
        membership = fetch(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == s.workspace_id,
                WorkspaceMembership.principal_id == s.principal_id,
            )
        )
        grant = fetch(
            select(ProjectAccessGrant).where(
                ProjectAccessGrant.project_id == s.project_id,
                ProjectAccessGrant.principal_id == s.principal_id,
            )
        )
        now = datetime.utcnow()
        roles = (
            {"reader", "writer", "owner"} if action == "read" else {"writer", "owner"}
        )

        def valid(record):
            return (
                record is not None
                and record.role in roles
                and record.revoked_at is None
                and (record.expires_at is None or record.expires_at > now)
            )

        if (
            workspace is None
            or project is None
            or not valid(membership)
            or not valid(grant)
        ):
            raise ScopeDenied("Scoped access denied")
        return workspace

    def _tasks(self):
        return select(Task).where(
            Task.workspace_id == self.scope.workspace_id,
            Task.project_id == self.scope.project_id,
        )

    @staticmethod
    def _task_view(task):
        return TaskView(
            task.id, task.workspace_id, task.project_id, task.status, task.owner_text
        )

    def task(self, task_id):
        self._authorize("read")
        task = self.session.scalar(self._tasks().where(Task.id == task_id))
        if task is None:
            raise ScopeDenied("Scoped access denied")
        return self._task_view(task)

    def tasks(self, limit=50):
        self._authorize("read")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        return [
            self._task_view(task)
            for task in self.session.scalars(
                self._tasks().order_by(Task.id).limit(limit)
            )
        ]

    def memories(self, limit=50):
        self._authorize("read")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        query = select(MemoryEntry).where(
            MemoryEntry.workspace_id == self.scope.workspace_id,
            MemoryEntry.project_id == self.scope.project_id,
            or_(
                MemoryEntry.task_id.is_(None),
                MemoryEntry.task_id.in_(self._tasks().with_only_columns(Task.id)),
            ),
        )
        return [
            MemoryView(
                row.id, row.workspace_id, row.project_id, row.content, row.source_ref
            )
            for row in self.session.scalars(query.order_by(MemoryEntry.id).limit(limit))
        ]

    def create_task(self, owner_text):
        self._authorize("write")
        if not isinstance(owner_text, str) or not owner_text.strip():
            raise ValueError("Task text is required")
        task = Task(
            workspace_id=self.scope.workspace_id,
            project_id=self.scope.project_id,
            owner_text=owner_text,
        )
        self.session.add(task)
        self.session.flush()
        self.session.add(
            AuditEvent(
                task_id=task.id,
                event_type="scoped_task_created",
                payload_json={
                    "workspace_id": self.scope.workspace_id,
                    "project_id": self.scope.project_id,
                    "principal_id": self.scope.principal_id,
                },
            )
        )
        self.session.flush()
        return self._task_view(task)

    def cache_key(self, namespace, revision):
        """Authorize before every cache lookup; no caller may reuse this as a capability."""
        workspace = self._authorize("read")
        data = [
            namespace,
            revision,
            self.scope.principal_id,
            self.scope.workspace_id,
            self.scope.project_id,
            workspace.policy_version,
        ]
        return hashlib.sha256(
            json.dumps(data, ensure_ascii=True, separators=(",", ":")).encode()
        ).hexdigest()
