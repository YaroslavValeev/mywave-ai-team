"""Explicit, reviewed classification. No API/automatic backfill is enabled."""

from sqlalchemy import select

from app.storage.models import AuditEvent, MemoryEntry, Project, Run, Task, Workspace


class WorkspaceClassificationError(ValueError):
    pass


def classify_project(
    session, *, project_id, workspace_id, actor, source_ref, apply=False
):
    """Caller owns transaction/commit; preview is the default, never grants access.

    Requires an idle maintenance window: legacy writers do not yet enforce scopes.
    Project-linked tasks and memory are classified atomically, never reassigned.
    """
    if (
        not isinstance(actor, str)
        or not actor.strip()
        or not isinstance(source_ref, str)
        or not source_ref.strip()
    ):
        raise WorkspaceClassificationError("Reviewer and source are required")
    if session.new or session.dirty or session.deleted:
        raise WorkspaceClassificationError("Use a clean transaction for classification")
    workspace = session.get(Workspace, workspace_id)
    project = session.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if workspace is None or project is None:
        raise WorkspaceClassificationError("Unknown workspace or project")
    tasks = list(
        session.scalars(
            select(Task).where(Task.project_id == project_id).with_for_update()
        )
    )
    memories = list(
        session.scalars(
            select(MemoryEntry)
            .where(MemoryEntry.project_id == project_id)
            .with_for_update()
        )
    )
    records = [project, *tasks, *memories]
    if any(record.workspace_id not in (None, workspace_id) for record in records):
        raise WorkspaceClassificationError(
            "Existing classification conflicts; nothing reassigned"
        )
    if any(
        task.status
        in {"IN_PIPELINE", "IN_ROUNDTABLE", "IN_COURT", "EXECUTING", "VALIDATING"}
        for task in tasks
    ):
        raise WorkspaceClassificationError("Project has an active mission")
    active = session.scalar(
        select(Run.id)
        .join(Task, Run.task_id == Task.id)
        .where(Task.project_id == project_id, Run.is_active.is_not(False))
        .limit(1)
    )
    if active is not None:
        raise WorkspaceClassificationError("Project has an active persisted run")
    foreign_memory = session.scalar(
        select(MemoryEntry.id)
        .join(Task, MemoryEntry.task_id == Task.id)
        .where(Task.project_id == project_id, MemoryEntry.project_id != project_id)
        .limit(1)
    )
    if foreign_memory is not None:
        raise WorkspaceClassificationError("Memory task/project relationship conflicts")
    # Memory must not reference a task in a different project, even if legacy data permits it.
    for memory in memories:
        if memory.task_id is not None:
            task = session.get(Task, memory.task_id)
            if task is None or task.project_id != project_id:
                raise WorkspaceClassificationError(
                    "Memory task/project relationship conflicts"
                )
    changes = [record for record in records if record.workspace_id is None]
    result = {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "projects": int(project.workspace_id is None),
        "tasks": sum(task.workspace_id is None for task in tasks),
        "memories": sum(memory.workspace_id is None for memory in memories),
        "applied": bool(apply and changes),
    }
    if apply and changes:
        for record in changes:
            record.workspace_id = workspace_id
        session.add(
            AuditEvent(
                event_type="workspace_classification",
                payload_json={
                    **result,
                    "actor": actor.strip(),
                    "source_ref": source_ref.strip(),
                    "access_granted": False,
                },
            )
        )
        session.flush()
    return result
