"""The repository is tested directly; legacy HTTP routes remain disabled for scoped intake."""

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from test_workspace_schema import (
    engine,
    session,
)  # noqa: F401: shared disposable DB fixtures
from app.storage.models import (
    AuditEvent,
    MemoryEntry,
    Project,
    ProjectAccessGrant,
    Task,
    Workspace,
    WorkspaceMembership,
)
from app.workspaces.access import Scope, ScopedRepository, ScopeDenied


def seed(session, kind="MYWAVE"):
    workspace = Workspace(slug="scope", name="Scope", kind=kind, owner_id="alice")
    session.add(workspace)
    session.flush()
    projects = [
        Project(slug=name, name=name, workspace_id=workspace.id)
        for name in ("media", "sponsor")
    ]
    session.add_all(projects)
    session.flush()
    for project in projects:
        session.add(
            Task(
                project_id=project.id,
                workspace_id=workspace.id,
                owner_text=project.name,
            )
        )
        session.add(
            MemoryEntry(
                project_id=project.id,
                workspace_id=workspace.id,
                scope="note",
                content=project.name,
            )
        )
    membership = WorkspaceMembership(
        workspace_id=workspace.id, principal_id="alice", role="writer"
    )
    grant = ProjectAccessGrant(
        project_id=projects[0].id, principal_id="alice", role="writer"
    )
    session.add_all([membership, grant])
    session.commit()
    repo = ScopedRepository(session, Scope("alice", workspace.id, projects[0].id))
    return repo, workspace, projects, membership, grant


@pytest.mark.parametrize("kind", ["FEDERATION", "MYWAVE", "JOINT"])
def test_project_filter_applies_before_limit_and_memory_retrieval(session, kind):
    repo, workspace, projects, _, _ = seed(session, kind)
    assert [task.owner_text for task in repo.tasks(limit=1)] == ["media"]
    assert [memory.content for memory in repo.memories()] == ["media"]
    foreign = session.scalar(select(Task).where(Task.project_id == projects[1].id))
    with pytest.raises(ScopeDenied):
        repo.task(foreign.id)
    # DTO does not offer lazy relationships into arbitrary ORM records.
    assert not hasattr(repo.tasks()[0], "project")


def test_workspace_membership_and_owner_name_do_not_grant_another_product(session):
    _, workspace, projects, _, _ = seed(session)
    repo = ScopedRepository(session, Scope("alice", workspace.id, projects[1].id))
    with pytest.raises(ScopeDenied):
        repo.tasks()
    with pytest.raises(ScopeDenied):
        repo.create_task("Not authorized")


@pytest.mark.parametrize("field", ["expires_at", "revoked_at"])
@pytest.mark.parametrize("target", ["membership", "grant"])
def test_revocation_or_expiry_rechecked_after_a_successful_read(session, field, target):
    repo, _, _, membership, grant = seed(session)
    assert repo.tasks()
    setattr(
        membership if target == "membership" else grant,
        field,
        datetime.utcnow() - timedelta(seconds=1),
    )
    session.commit()
    with pytest.raises(ScopeDenied):
        repo.tasks()
    with pytest.raises(ScopeDenied):
        repo.cache_key("tasks", 1)


@pytest.mark.parametrize("target", ["membership", "grant"])
def test_reader_cannot_write_even_with_other_writer_grant(session, target):
    repo, _, _, membership, grant = seed(session)
    (membership if target == "membership" else grant).role = "reader"
    session.commit()
    assert repo.tasks()
    with pytest.raises(ScopeDenied):
        repo.create_task("Denied")


def test_unclassified_or_mismatched_records_are_not_retrieved(session):
    repo, workspace, projects, _, _ = seed(session)
    foreign = Workspace(
        slug="foreign", name="Foreign", kind="FEDERATION", owner_id="alice"
    )
    session.add(foreign)
    session.flush()
    session.add_all(
        [
            Task(project_id=projects[0].id, owner_text="legacy-null"),
            Task(
                project_id=projects[0].id,
                workspace_id=foreign.id,
                owner_text="foreign-scope",
            ),
        ]
    )
    session.commit()
    assert [task.owner_text for task in repo.tasks()] == ["media"]
    with pytest.raises(ScopeDenied):
        ScopedRepository(session, Scope("alice", foreign.id, projects[0].id)).tasks()


def test_missing_membership_denies_even_with_product_grant(session):
    repo, _, _, membership, _ = seed(session)
    session.delete(membership)
    session.commit()
    with pytest.raises(ScopeDenied):
        repo.tasks()


def test_external_revocation_does_not_reuse_loaded_grant(session, engine):
    repo, _, _, _, grant = seed(session)
    assert repo.tasks()
    grant_id = grant.id
    session.commit()
    with Session(engine) as revoker:
        row = revoker.get(ProjectAccessGrant, grant_id)
        row.revoked_at = datetime.utcnow()
        revoker.commit()
    with pytest.raises(ScopeDenied):
        repo.tasks()


def test_scoped_create_cannot_inject_scope_and_commits_audit_atomically(session):
    repo, workspace, projects, _, _ = seed(session)
    view = repo.create_task("Untrusted text: workspace_id=999")
    session.commit()
    assert view.workspace_id == workspace.id and view.project_id == projects[0].id
    audit = session.scalar(select(AuditEvent).where(AuditEvent.task_id == view.id))
    assert audit.payload_json["principal_id"] == "alice"
    assert "Untrusted text" not in str(audit.payload_json)


def test_failed_audit_rolls_back_created_task(session):
    repo, _, _, _, _ = seed(session)

    def fail(*_):
        raise RuntimeError("Audit unavailable")

    event.listen(AuditEvent, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            repo.create_task("Must roll back")
        session.rollback()
    finally:
        event.remove(AuditEvent, "before_insert", fail)
    assert (
        session.scalar(select(Task.id).where(Task.owner_text == "Must roll back"))
        is None
    )


def test_cache_partition_and_unknown_identity(session):
    repo, workspace, projects, _, _ = seed(session)
    session.add_all(
        [
            WorkspaceMembership(
                workspace_id=workspace.id, principal_id="bob", role="reader"
            ),
            ProjectAccessGrant(
                project_id=projects[0].id, principal_id="bob", role="reader"
            ),
            ProjectAccessGrant(
                project_id=projects[1].id, principal_id="alice", role="reader"
            ),
        ]
    )
    session.commit()
    key = repo.cache_key("tasks", 1)
    assert key != ScopedRepository(
        session, Scope("bob", workspace.id, projects[0].id)
    ).cache_key("tasks", 1)
    assert key != ScopedRepository(
        session, Scope("alice", workspace.id, projects[1].id)
    ).cache_key("tasks", 1)
    with pytest.raises(ScopeDenied):
        ScopedRepository(
            session, Scope("unknown", workspace.id, projects[0].id)
        ).tasks()
    workspace.policy_version += 1
    session.commit()
    assert key != repo.cache_key("tasks", 1)


@pytest.mark.parametrize(
    "values", [("", 1, 1), ("alice", None, 1), ("alice", 1, True), ("alice", 1, -1)]
)
def test_scope_requires_explicit_identity_and_positive_ids(values):
    with pytest.raises(ScopeDenied):
        Scope(*values)


def test_invalid_and_duplicate_project_grants_rejected(session):
    _, _, projects, _, _ = seed(session)
    session.add(
        ProjectAccessGrant(
            project_id=projects[0].id, principal_id="alice", role="reader"
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.add(
        ProjectAccessGrant(
            project_id=projects[1].id, principal_id="alice", role="invalid"
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_009_migration_empty_reverse_and_populated_gate(engine):
    path = (
        Path(__file__).resolve().parents[2]
        / "app/storage/migrations/versions/009_project_access_grants.py"
    )
    spec = importlib.util.spec_from_file_location("project_grants_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE projects (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO projects (id) VALUES (1)"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.downgrade()
            module.upgrade()
            connection.execute(
                text(
                    "INSERT INTO project_access_grants (project_id,principal_id,role) VALUES (1,'qa','reader')"
                )
            )
            with pytest.raises(RuntimeError, match="Project grants exist"):
                module.downgrade()
        assert "project_access_grants" in inspect(connection).get_table_names()
