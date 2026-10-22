import importlib.util
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.storage.models import (
    AuditEvent,
    Base,
    Project,
    ProjectAccessGrant,
    Task,
    Workspace,
    WorkspaceMembership,
)

spec = importlib.util.spec_from_file_location(
    "owner_bootstrap",
    Path(__file__).resolve().parents[2] / "scripts/server/bootstrap_mywave_club_box.py",
)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


@pytest.fixture
def engine(tmp_path):
    url = os.getenv("BOOTSTRAP_TEST_DATABASE_URL")
    if url:
        from sqlalchemy.engine import make_url

        parsed = make_url(url)
        assert (
            parsed.host == "127.0.0.1"
            and parsed.database == "bootstrap_qa"
            and parsed.username == "drill"
        ), "Disposable test DB only"
    engine = create_engine(url or f"sqlite:///{tmp_path / 'bootstrap.db'}")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def apply(engine):
    with Session(engine) as session, session.begin():
        return bootstrap.bootstrap(
            session, execute=True, approval=bootstrap.plan_hash()
        )


def test_preview_is_read_only_and_contains_exact_reviewable_policy(engine):
    with Session(engine) as session:
        result = bootstrap.bootstrap(session)
        assert result["action"] == "would_create" and result["changed"] is False
        assert result["plan"]["workspace"]["kind"] == "MYWAVE"
        assert result["plan"]["project_role"] == "writer"
        assert result["plan"]["bind_authentication"] is False
        assert all(
            count(session, model) == 0
            for model in (
                Workspace,
                Project,
                WorkspaceMembership,
                ProjectAccessGrant,
                AuditEvent,
            )
        )


def test_exact_owner_approval_is_required_before_any_insert(engine):
    with Session(engine) as session:
        with pytest.raises(bootstrap.BootstrapDenied, match="plan hash"):
            bootstrap.bootstrap(session, execute=True, approval="wrong")
        assert count(session, Workspace) == 0


def test_approval_cannot_be_reused_after_policy_change(engine, monkeypatch):
    approved = bootstrap.plan_hash()
    monkeypatch.setitem(bootstrap.PLAN, "project_role", "owner")
    with Session(engine) as session:
        with pytest.raises(bootstrap.BootstrapDenied):
            bootstrap.bootstrap(session, execute=True, approval=approved)
        assert count(session, Workspace) == 0


def test_create_is_atomic_audited_and_idempotent(engine):
    first = apply(engine)
    second = apply(engine)
    assert first["changed"] is True and second["changed"] is False
    assert first["workspace_id"] == second["workspace_id"]
    assert first["project_id"] == second["project_id"]
    assert first["authentication_binding_created"] is False
    with Session(engine) as session:
        for model in (
            Workspace,
            Project,
            WorkspaceMembership,
            ProjectAccessGrant,
            AuditEvent,
        ):
            assert count(session, model) == 1
        audit = session.scalar(select(AuditEvent))
        assert audit.payload_json["plan_sha256"] == bootstrap.plan_hash()
        assert audit.payload_json["principal_id"] == "owner:yaroslav"


def test_injected_failure_rolls_back_every_created_record(engine, monkeypatch):
    with Session(engine) as session:
        real_flush = session.flush

        def failing_flush(*args, **kwargs):
            if any(isinstance(row, AuditEvent) for row in session.new):
                # Workspace and project have already been flushed at this point.
                raise RuntimeError("simulated audit failure")
            return real_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", failing_flush)
        with pytest.raises(RuntimeError), session.begin():
            bootstrap.bootstrap(session, execute=True, approval=bootstrap.plan_hash())
    with Session(engine) as session:
        assert all(
            count(session, m) == 0
            for m in (
                Workspace,
                Project,
                WorkspaceMembership,
                ProjectAccessGrant,
                AuditEvent,
            )
        )


def test_legacy_project_and_mission_are_not_classified_or_modified(engine):
    with Session(engine) as session, session.begin():
        project = Project(slug="legacy", name="Existing")
        session.add(project)
        session.flush()
        session.add(
            Task(
                id=39, project_id=project.id, owner_text="original", status="WAIT_OWNER"
            )
        )
    apply(engine)
    with Session(engine) as session:
        task = session.get(Task, 39)
        assert (
            task.workspace_id is None
            and task.owner_text == "original"
            and task.status == "WAIT_OWNER"
        )
        assert task.project.slug == "legacy" and task.project.workspace_id is None


@pytest.mark.parametrize(
    "conflict", ["legacy_project", "workspace_only", "foreign_workspace"]
)
def test_partial_and_conflicting_records_are_left_untouched(engine, conflict):
    with Session(engine) as session, session.begin():
        if conflict == "legacy_project":
            session.add(Project(slug="mywave-club-box", name="Existing legacy project"))
        else:
            session.add(
                Workspace(
                    slug="mywave" if conflict == "workspace_only" else "other",
                    name="Other",
                    kind="FEDERATION",
                    owner_id="other",
                )
            )
    with pytest.raises(bootstrap.BootstrapDenied):
        apply(engine)
    with Session(engine) as session:
        assert (
            count(session, AuditEvent) == 0 and count(session, ProjectAccessGrant) == 0
        )


@pytest.mark.parametrize("change", ["revoke", "expire", "role", "owner", "extra_grant"])
def test_existing_permissions_are_never_reactivated_or_expanded(engine, change):
    from datetime import datetime

    apply(engine)
    with Session(engine) as session, session.begin():
        grant = session.scalar(select(ProjectAccessGrant))
        if change == "revoke":
            grant.revoked_at = datetime.utcnow()
        elif change == "expire":
            grant.expires_at = datetime.utcnow()
        elif change == "role":
            grant.role = "reader"
        elif change == "owner":
            session.scalar(select(Workspace)).owner_id = "different"
        else:
            session.add(
                ProjectAccessGrant(
                    project_id=grant.project_id, principal_id="other", role="reader"
                )
            )
    with pytest.raises(bootstrap.BootstrapDenied):
        apply(engine)
    with Session(engine) as session:
        assert count(session, AuditEvent) == 1


def test_legacy_repository_cannot_see_new_project(engine):
    from app.workspaces.legacy import LegacySession

    apply(engine)
    with LegacySession(engine) as session:
        assert count(session, Project) == 0


def test_principal_without_product_grant_is_denied(engine):
    from app.workspaces.access import Scope, ScopeDenied, ScopedRepository

    result = apply(engine)
    with Session(engine) as session, session.begin():
        session.delete(session.scalar(select(ProjectAccessGrant)))
    with Session(engine) as session:
        with pytest.raises(ScopeDenied):
            ScopedRepository(
                session,
                Scope("owner:yaroslav", result["workspace_id"], result["project_id"]),
            ).tasks()


@pytest.mark.parametrize(
    "setting,value",
    [
        ("APP_COMMIT_SHA", "wrong"),
        ("WORKSPACE_ACCESS_ENABLED", "true"),
        ("WORKSPACE_OWNER_PRINCIPAL_ID", "someone"),
    ],
)
def test_runtime_guard_fails_before_database_access(monkeypatch, setting, value):
    from unittest.mock import Mock

    monkeypatch.setenv("APP_COMMIT_SHA", bootstrap.SOURCE)
    monkeypatch.setenv("WORKSPACE_ACCESS_ENABLED", "false")
    monkeypatch.setenv("WORKSPACE_OWNER_PRINCIPAL_ID", "")
    monkeypatch.setenv("WORKSPACE_PRINCIPAL_BINDINGS_JSON", "[]")
    monkeypatch.setenv(setting, value)
    engine = Mock()
    with pytest.raises(bootstrap.BootstrapDenied):
        bootstrap.runtime_guard(engine)
    engine.connect.assert_not_called()


def test_postgres_concurrent_operators_create_one_setup(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL advisory lock requires isolated PostgreSQL")
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: apply(engine), range(2)))
    assert sorted(result["changed"] for result in results) == [False, True]
    with Session(engine) as session:
        assert count(session, AuditEvent) == 1
        assert count(session, Workspace) == 1
