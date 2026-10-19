"""All existing channels use a legacy-only session, including background workers."""

from sqlalchemy import and_, event, false, or_, select
from sqlalchemy.orm import Session, with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause, TextClause

from app.storage.models import (
    Approval,
    AuditEvent,
    Decision,
    ExecutionEvent,
    Handoff,
    MemoryEntry,
    Project,
    ProjectAccessGrant,
    Run,
    Task,
    Workspace,
    WorkspaceMembership,
)
from app.workspaces.access import ScopeDenied


class LegacySession(Session):
    def get(self, entity, ident, **kwargs):
        kwargs["populate_existing"] = True
        value = super().get(entity, ident, **kwargs)
        if value is not None:
            _check_row(self, value)
        return value

    def bulk_save_objects(self, *args, **kwargs):
        raise ScopeDenied("Legacy bulk writes denied")

    def bulk_insert_mappings(self, *args, **kwargs):
        raise ScopeDenied("Legacy bulk writes denied")

    def bulk_update_mappings(self, *args, **kwargs):
        raise ScopeDenied("Legacy bulk writes denied")


def _projects():
    table = Project.__table__.c
    return select(table.id).where(table.workspace_id.is_(None)).correlate(None)


def _tasks():
    table = Task.__table__.c
    return (
        select(table.id)
        .where(
            table.workspace_id.is_(None),
            or_(table.project_id.is_(None), table.project_id.in_(_projects())),
        )
        .correlate(None)
    )


@event.listens_for(LegacySession, "do_orm_execute")
def _filter(execute_state):
    if not execute_state.is_orm_statement:
        raise ScopeDenied("Legacy SQL requires mapped entities")
    if execute_state.is_from_statement or any(
        isinstance(node, TextClause)
        or (isinstance(node, ColumnClause) and node.is_literal and node.name != "*")
        for node in visitors.iterate(execute_state.statement)
    ):
        raise ScopeDenied("Legacy textual SQL denied")
    if execute_state.is_insert:
        raise ScopeDenied("Legacy bulk inserts are not supported")
    if (execute_state.is_update or execute_state.is_delete) and isinstance(
        execute_state.parameters, list
    ):
        raise ScopeDenied("Legacy bulk writes denied")
    if execute_state.is_update:
        values = getattr(execute_state.statement, "_values", None) or {}
        if any(
            getattr(key, "name", str(key)) in {"workspace_id", "project_id", "task_id"}
            for key in values
        ):
            raise ScopeDenied("Legacy bulk reassignment denied")
    criteria = [
        (Project, Project.workspace_id.is_(None)),
        (Task, Task.id.in_(_tasks())),
        (
            MemoryEntry,
            and_(
                MemoryEntry.workspace_id.is_(None),
                MemoryEntry.project_id.in_(_projects()),
                or_(MemoryEntry.task_id.is_(None), MemoryEntry.task_id.in_(_tasks())),
            ),
        ),
        (
            AuditEvent,
            or_(
                AuditEvent.task_id.in_(_tasks()),
                and_(
                    AuditEvent.task_id.is_(None),
                    AuditEvent.payload_json["workspace_id"].as_integer().is_(None),
                    or_(
                        AuditEvent.payload_json["project_id"].as_integer().is_(None),
                        AuditEvent.payload_json["project_id"]
                        .as_integer()
                        .in_(_projects()),
                    ),
                ),
            ),
        ),
    ]
    criteria += [
        (model, model.task_id.in_(_tasks()))
        for model in (Approval, Decision, ExecutionEvent, Handoff, Run)
    ]
    criteria += [
        (model, false())
        for model in (Workspace, WorkspaceMembership, ProjectAccessGrant)
    ]
    execute_state.statement = execute_state.statement.options(
        *[
            with_loader_criteria(model, predicate, include_aliases=True)
            for model, predicate in criteria
        ]
    )


def _check_row(session, row):
    if isinstance(row, (Workspace, WorkspaceMembership, ProjectAccessGrant)):
        raise ScopeDenied("Legacy access to workspace administration denied")
    if isinstance(row, (Task, Project, MemoryEntry)) and row.workspace_id is not None:
        raise ScopeDenied("Legacy access to classified records denied")
    project_id = getattr(row, "project_id", None)
    if (
        project_id is not None
        and session.scalar(
            select(Project.id).where(
                Project.id == project_id, Project.workspace_id.is_(None)
            )
        )
        is None
    ):
        raise ScopeDenied("Legacy access to classified project denied")
    task_id = getattr(row, "task_id", None)
    if (
        task_id is not None
        and session.scalar(
            select(Task.id).where(Task.id == task_id, Task.id.in_(_tasks()))
        )
        is None
    ):
        raise ScopeDenied("Legacy access to classified task denied")
    if isinstance(row, AuditEvent) and isinstance(row.payload_json, dict):
        if row.payload_json.get("workspace_id") is not None:
            raise ScopeDenied("Legacy scoped audit access denied")
        pid = row.payload_json.get("project_id")
        if (
            pid is not None
            and session.scalar(
                select(Project.id).where(Project.id == pid, Project.id.in_(_projects()))
            )
            is None
        ):
            raise ScopeDenied("Legacy scoped audit access denied")


@event.listens_for(LegacySession, "before_flush")
def _validate(session, *_):
    with session.no_autoflush:
        for row in [*session.new, *session.dirty, *session.deleted]:
            _check_row(session, row)
