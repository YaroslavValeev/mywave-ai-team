"""Files are a separate boundary; a database id never authorizes arbitrary paths."""

import os
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.storage.models import Handoff, Project, Task
from app.workspaces.access import ScopeDenied


def legacy_path(path):
    path = Path(path).expanduser().resolve()
    root = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts")).expanduser().resolve()
    if path.is_relative_to(root / "workspaces"):
        raise ScopeDenied("Artifact access denied")
    from app.storage.repositories import get_engine

    with Session(get_engine()) as session:
        classified = (
            select(Task.id)
            .outerjoin(Project, Task.project_id == Project.id)
            .where(
                or_(Task.workspace_id.is_not(None), Project.workspace_id.is_not(None))
            )
        )
        owners = list(
            session.scalars(
                select(Handoff.md_path).where(
                    Handoff.task_id.in_(classified), Handoff.md_path.is_not(None)
                )
            )
        )
        owners += list(
            session.scalars(
                select(Task.report_path).where(
                    Task.id.in_(classified), Task.report_path.is_not(None)
                )
            )
        )
        for owned in owners:
            owned = Path(owned).expanduser().resolve()
            if path == owned or (
                path.is_file() and owned.is_file() and os.path.samefile(path, owned)
            ):
                raise ScopeDenied("Artifact access denied")
    return path


def read_legacy_text(path):
    return legacy_path(path).read_text(encoding="utf-8", errors="ignore")


def read_scoped_file(repo, task_id, path):
    repo.task(task_id)  # Always recheck revocation, including after a cache lookup.
    scope = repo.scope
    base = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts")).expanduser().resolve()
    root = (
        base
        / "workspaces"
        / str(scope.workspace_id)
        / "projects"
        / str(scope.project_id)
        / "tasks"
        / f"task_{task_id}"
    )
    original = Path(path).expanduser().absolute()
    resolved = original.resolve()
    if not resolved.is_relative_to(root) or any(
        part.is_symlink() for part in (original, *original.parents)
    ):
        raise ScopeDenied("Artifact access denied")
    if not resolved.is_file() or resolved.stat().st_size > 5 * 1024 * 1024:
        raise ScopeDenied("Artifact access denied")
    return resolved.read_bytes()
