"""SQLite always; dedicated, disposable PostgreSQL when explicitly configured."""

import importlib.util
import os
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.storage.models import (
    AuditEvent,
    Base,
    MemoryEntry,
    Project,
    Run,
    Task,
    Workspace,
    WorkspaceMembership,
)
from app.storage.workspace_backfill import (
    WorkspaceClassificationError,
    classify_project,
)

URLS = ["sqlite:///:memory:"]
if os.getenv("WORKSPACE_TEST_DATABASE_URL"):
    test_url = make_url(os.environ["WORKSPACE_TEST_DATABASE_URL"])
    if test_url.get_backend_name() != "postgresql" or not (
        test_url.database or ""
    ).startswith("ai_team_workspace_qa_"):
        raise RuntimeError(
            "Only an explicitly named disposable workspace QA PostgreSQL DB is allowed"
        )
    URLS.append(test_url)


@pytest.fixture(params=URLS, ids=lambda url: make_url(url).get_backend_name())
def engine(request):
    engine = create_engine(request.param)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def seed(session):
    workspace = Workspace(
        slug="federation", name="Federation", kind="FEDERATION", owner_id="owner"
    )
    project = Project(slug="legacy", name="Legacy")
    session.add_all([workspace, project])
    session.flush()
    task = Task(
        project_id=project.id, owner_text="Preserve original text", status="WAIT_OWNER"
    )
    session.add(task)
    session.flush()
    memory = MemoryEntry(
        project_id=project.id, task_id=task.id, scope="note", content="Preserve memory"
    )
    session.add(memory)
    session.commit()
    return workspace, project, task, memory


def classify(session, workspace, project, **kwargs):
    return classify_project(
        session,
        project_id=project.id,
        workspace_id=workspace.id,
        actor="reviewer",
        source_ref="review:explicit-project-map",
        **kwargs,
    )


def test_legacy_is_not_assigned_and_preview_does_not_write(session):
    workspace, project, task, memory = seed(session)
    result = classify(session, workspace, project)
    assert result == dict(
        project_id=project.id,
        workspace_id=workspace.id,
        projects=1,
        tasks=1,
        memories=1,
        applied=False,
    )
    session.commit()
    assert all(record.workspace_id is None for record in (project, task, memory))
    assert session.scalar(select(AuditEvent.id)) is None
    assert session.scalar(select(WorkspaceMembership.id)) is None


def test_reviewed_backfill_is_atomic_idempotent_and_preserves_content(session):
    workspace, project, task, memory = seed(session)
    assert classify(session, workspace, project, apply=True)["applied"]
    session.commit()
    assert all(
        record.workspace_id == workspace.id for record in (project, task, memory)
    )
    assert task.owner_text == "Preserve original text" and task.status == "WAIT_OWNER"
    assert memory.content == "Preserve memory"
    audit = session.scalar(select(AuditEvent))
    assert audit.payload_json["access_granted"] is False
    assert audit.payload_json["source_ref"] == "review:explicit-project-map"
    assert not classify(session, workspace, project, apply=True)["applied"]
    session.commit()
    assert len(list(session.scalars(select(AuditEvent)))) == 1


def test_backfill_rollback_does_not_leave_classification_without_audit(session):
    workspace, project, task, memory = seed(session)

    def fail_audit(*_):
        raise RuntimeError("Audit unavailable")

    event.listen(AuditEvent, "before_insert", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            classify(session, workspace, project, apply=True)
        session.rollback()
    finally:
        event.remove(AuditEvent, "before_insert", fail_audit)
    assert all(record.workspace_id is None for record in (project, task, memory))
    assert session.scalar(select(AuditEvent.id)) is None


@pytest.mark.parametrize("record_index", [1, 2, 3])
def test_conflicting_scope_is_never_overwritten(session, record_index):
    records = seed(session)
    other = Workspace(slug="mywave", name="MyWave", kind="MYWAVE", owner_id="owner")
    session.add(other)
    session.flush()
    records[record_index].workspace_id = other.id
    session.commit()
    with pytest.raises(WorkspaceClassificationError, match="conflicts"):
        classify(session, *records[:2], apply=True)
    session.rollback()
    assert records[record_index].workspace_id == other.id
    assert session.scalar(select(AuditEvent.id)) is None


@pytest.mark.parametrize(
    "status", ["IN_PIPELINE", "EXECUTING", "VALIDATING", "IN_COURT", "IN_ROUNDTABLE"]
)
def test_active_task_blocks_backfill(session, status):
    workspace, project, task, _ = seed(session)
    task.status = status
    session.commit()
    with pytest.raises(WorkspaceClassificationError, match="active mission"):
        classify(session, workspace, project, apply=True)
    assert project.workspace_id is None


def test_persisted_active_run_blocks_even_wait_owner(session):
    workspace, project, task, _ = seed(session)
    session.add(Run(run_id="active", task_id=task.id, state="running", is_active=True))
    session.commit()
    with pytest.raises(WorkspaceClassificationError, match="persisted run"):
        classify(session, workspace, project, apply=True)


def test_unlinked_legacy_tasks_remain_unclassified(session):
    workspace, project, _, _ = seed(session)
    unlinked = Task(owner_text="No reviewed project")
    session.add(unlinked)
    session.commit()
    classify(session, workspace, project, apply=True)
    session.commit()
    assert unlinked.workspace_id is None


def test_foreign_memory_referencing_project_task_blocks(session):
    workspace, project, task, _ = seed(session)
    other = Project(slug="foreign-memory", name="Foreign memory")
    session.add(other)
    session.flush()
    session.add(
        MemoryEntry(
            project_id=other.id,
            task_id=task.id,
            scope="note",
            content="Cross-project link",
        )
    )
    session.commit()
    with pytest.raises(WorkspaceClassificationError, match="Memory task/project"):
        classify(session, workspace, project, apply=True)


def test_classified_workspace_cannot_be_deleted(session):
    workspace, project, _, _ = seed(session)
    classify(session, workspace, project, apply=True)
    session.commit()
    session.delete(workspace)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_cross_project_memory_and_dirty_transactions_block(session):
    workspace, project, task, memory = seed(session)
    project_id, workspace_id = project.id, workspace.id
    task.owner_text = "Uncommitted edit"
    with pytest.raises(WorkspaceClassificationError, match="clean transaction"):
        classify_project(
            session,
            project_id=project_id,
            workspace_id=workspace_id,
            actor="reviewer",
            source_ref="review",
            apply=True,
        )
    session.rollback()
    other = Project(slug="other", name="Other")
    session.add(other)
    session.flush()
    task.project_id = other.id
    session.commit()
    with pytest.raises(WorkspaceClassificationError, match="Memory task/project"):
        classify(session, workspace, project, apply=True)
    assert memory.workspace_id is None


def test_missing_reviewer_or_unknown_target_blocks(session):
    workspace, project, _, _ = seed(session)
    for kwargs in (
        {"actor": "", "source_ref": "review"},
        {"actor": "reviewer", "source_ref": " "},
    ):
        with pytest.raises(WorkspaceClassificationError, match="Reviewer and source"):
            classify_project(
                session,
                project_id=project.id,
                workspace_id=workspace.id,
                apply=True,
                **kwargs,
            )
    with pytest.raises(WorkspaceClassificationError, match="Unknown"):
        classify_project(
            session,
            project_id=project.id,
            workspace_id=99999,
            actor="reviewer",
            source_ref="review",
            apply=True,
        )


def test_schema_rejects_invalid_kind_duplicate_membership_and_dangling_scope(session):
    workspace, project, _, _ = seed(session)
    session.add(
        Workspace(slug="invalid", name="Invalid", kind="UNKNOWN", owner_id="owner")
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.add_all(
        [
            WorkspaceMembership(
                workspace_id=workspace.id, principal_id="same", role="reader"
            )
            for _ in range(2)
        ]
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    project.workspace_id = 99999
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.add(
        WorkspaceMembership(
            workspace_id=workspace.id, principal_id="admin", role="invalid"
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "app/storage/migrations/versions/008_workspace_foundation.py"
    )
    spec = importlib.util.spec_from_file_location("workspace_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_preserves_legacy_rows_and_empty_downgrade(engine):
    module = migration()
    with engine.begin() as connection:
        for name in module.SCOPED_TABLES:
            connection.execute(
                text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, original TEXT)")
            )
            connection.execute(
                text(f"INSERT INTO {name} (id,original) VALUES (1,'unchanged')")
            )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            for name in module.SCOPED_TABLES:
                assert connection.execute(
                    text(f"SELECT original,workspace_id FROM {name}")
                ).one() == ("unchanged", None)
                assert (
                    inspect(connection).get_foreign_keys(name)[0]["referred_table"]
                    == "workspaces"
                )
            module.downgrade()
            for name in module.SCOPED_TABLES:
                assert (
                    connection.execute(
                        text(f"SELECT original FROM {name}")
                    ).scalar_one()
                    == "unchanged"
                )
                assert "workspace_id" not in {
                    column["name"] for column in inspect(connection).get_columns(name)
                }


def test_downgrade_refuses_workspace_data(engine):
    module = migration()
    with engine.begin() as connection:
        for name in module.SCOPED_TABLES:
            connection.execute(text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            connection.execute(
                text(
                    "INSERT INTO workspaces (slug,name,kind,owner_id) VALUES ('fed','Federation','FEDERATION','owner')"
                )
            )
            with pytest.raises(RuntimeError, match="Workspace data exists"):
                module.downgrade()
            assert "workspaces" in inspect(connection).get_table_names()


def test_full_existing_postgres_chain_upgrade(engine, monkeypatch):
    if engine.dialect.name != "postgresql":
        pytest.skip("Full legacy migration chain requires PostgreSQL")
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "app/storage/migrations"))
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    command.upgrade(config, "007")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tasks (owner_text,status) VALUES ('legacy chain','WAIT_OWNER')"
            )
        )
    command.upgrade(config, "008")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "008"
        )
        assert connection.execute(
            text("SELECT owner_text,workspace_id FROM tasks")
        ).one() == ("legacy chain", None)
