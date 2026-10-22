"""Preview-first creation of one empty owner workspace. Never enables HTTP intake.

Run inside the qualified app container with this script supplied on stdin.
Standard SQLAlchemy Session is deliberate: this is a privileged operator tool,
not an application endpoint and not a LegacySession bypass exposed to agents.
"""

import argparse
import hashlib
import json
import os

SOURCE = "b2a11824342f7b7921bcb3d84dcdc8913fa8e86b"
PLAN = {
    "version": 1,
    "source_sha": SOURCE,
    "migration": "009",
    "principal_id": "owner:yaroslav",
    "workspace": {
        "slug": "mywave",
        "name": "MYWAVE",
        "kind": "MYWAVE",
        "owner_id": "owner:yaroslav",
        "policy_version": 1,
    },
    "project": {
        "slug": "mywave-club-box",
        "name": "Club Box",
        "owner_id": "owner:yaroslav",
        "project_type": "product",
        "stage": "build",
        "status": "ACTIVE",
    },
    "membership_role": "owner",
    "project_role": "writer",
    "activate_api": False,
    "bind_authentication": False,
    "move_existing_data": False,
    "allow_external_execution": False,
}


class BootstrapDenied(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise BootstrapDenied(message)


def plan_hash():
    return hashlib.sha256(
        json.dumps(PLAN, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def models():
    from app.storage.models import (
        AuditEvent,
        Project,
        ProjectAccessGrant,
        Workspace,
        WorkspaceMembership,
    )

    return AuditEvent, Project, ProjectAccessGrant, Workspace, WorkspaceMembership


def resolve(session):
    from sqlalchemy import func, select

    _, Project, Grant, Workspace, Membership = models()
    workspace = session.scalar(
        select(Workspace).where(Workspace.slug == PLAN["workspace"]["slug"])
    )
    project = session.scalar(
        select(Project).where(Project.slug == PLAN["project"]["slug"])
    )
    if workspace is None and project is None:
        require(
            session.scalar(select(func.count()).select_from(Workspace)) == 0,
            "Another workspace exists; first-space plan needs review",
        )
        require(
            session.scalar(select(func.count()).select_from(Grant)) == 0
            and session.scalar(select(func.count()).select_from(Membership)) == 0,
            "Unexpected access records; nothing changed",
        )
        return None, None
    require(
        workspace is not None and project is not None,
        "Partial or conflicting setup; nothing overwritten",
    )
    require(
        all(
            getattr(workspace, key) == value for key, value in PLAN["workspace"].items()
        ),
        "Existing workspace differs from approved plan",
    )
    require(
        all(getattr(project, key) == value for key, value in PLAN["project"].items())
        and project.workspace_id == workspace.id,
        "Existing project differs from approved plan",
    )
    members = session.scalars(
        select(Membership).where(Membership.workspace_id == workspace.id)
    ).all()
    grants = session.scalars(select(Grant).where(Grant.project_id == project.id)).all()
    for rows, role in (
        (members, PLAN["membership_role"]),
        (grants, PLAN["project_role"]),
    ):
        require(
            len(rows) == 1
            and rows[0].principal_id == PLAN["principal_id"]
            and rows[0].role == role
            and rows[0].revoked_at is None
            and rows[0].expires_at is None,
            "Existing permissions differ; no grant reactivation or expansion",
        )
    return workspace, project


def bootstrap(session, *, execute=False, approval=None):
    from sqlalchemy import text

    if execute:
        require(
            approval == plan_hash(),
            "Exact owner-approved plan hash is required before any write",
        )
        if session.get_bind().dialect.name == "postgresql":
            # Coordinates only copies of this bootstrap; DB uniqueness is also enforced.
            session.execute(text("SELECT pg_advisory_xact_lock(1297695041)"))
    workspace, project = resolve(session)
    existed = workspace is not None
    if execute and not existed:
        AuditEvent, Project, Grant, Workspace, Membership = models()
        workspace = Workspace(**PLAN["workspace"])
        session.add(workspace)
        session.flush()
        project = Project(**PLAN["project"], workspace_id=workspace.id)
        session.add(project)
        session.flush()
        session.add_all(
            [
                Membership(
                    workspace_id=workspace.id,
                    principal_id=PLAN["principal_id"],
                    role=PLAN["membership_role"],
                ),
                Grant(
                    project_id=project.id,
                    principal_id=PLAN["principal_id"],
                    role=PLAN["project_role"],
                ),
                AuditEvent(
                    event_type="workspace_bootstrap_approved",
                    payload_json={
                        "workspace_id": workspace.id,
                        "project_id": project.id,
                        "principal_id": PLAN["principal_id"],
                        "plan_sha256": plan_hash(),
                        "source": "owner_server_bootstrap",
                        "source_sha": SOURCE,
                        "workspace_api_enabled": False,
                    },
                ),
            ]
        )
        session.flush()
    return {
        "mode": "execute" if execute else "preview",
        "changed": execute and not existed,
        "action": (
            "already_present" if existed else "created" if execute else "would_create"
        ),
        "plan_sha256": plan_hash(),
        "plan": PLAN,
        "workspace_id": workspace.id if workspace else None,
        "project_id": project.id if project else None,
        "workspace_api_enabled": False,
        "authentication_binding_created": False,
    }


def runtime_guard(engine):
    from sqlalchemy import text

    require(
        os.getenv("APP_COMMIT_SHA") == SOURCE,
        "Unexpected app source; bootstrap blocked",
    )
    require(
        os.getenv("WORKSPACE_ACCESS_ENABLED", "false").lower() == "false",
        "Disable scoped intake before bootstrap",
    )
    require(
        not os.getenv("WORKSPACE_OWNER_PRINCIPAL_ID", "").strip()
        and json.loads(os.getenv("WORKSPACE_PRINCIPAL_BINDINGS_JSON", "[]")) == [],
        "Authentication bindings already exist; review required",
    )
    with engine.connect() as connection:
        require(
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "009",
            "Unexpected schema revision",
        )
        require(
            connection.execute(
                text("SELECT count(*) FROM runs WHERE is_active=true")
            ).scalar_one()
            == 0,
            "Active run blocks bootstrap",
        )
        require(
            connection.execute(
                text(
                    "SELECT count(*) FROM tasks WHERE status IN ('IN_PIPELINE','IN_ROUNDTABLE','IN_COURT','EXECUTING','VALIDATING')"
                )
            ).scalar_one()
            == 0,
            "Active mission blocks bootstrap",
        )


def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner-approved-plan")
    args = parser.parse_args()
    if args.execute:
        require(
            args.owner_approved_plan == plan_hash(),
            "Exact owner-approved plan hash is required",
        )
    engine = create_engine(os.environ["DATABASE_URL"])
    runtime_guard(engine)
    # Commit all four records and the approval audit atomically; preview rolls back.
    with Session(engine) as session:
        result = bootstrap(
            session, execute=args.execute, approval=args.owner_approved_plan
        )
        if args.execute:
            session.commit()
        else:
            session.rollback()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        "WORKSPACE_BOOTSTRAP_APPLIED"
        if args.execute
        else "WORKSPACE_BOOTSTRAP_PREVIEW_PASSED"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "ERROR:",
            str(error) if isinstance(error, BootstrapDenied) else type(error).__name__,
        )
        raise SystemExit(1)
