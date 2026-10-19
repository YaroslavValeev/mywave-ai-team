"""Add explicit workspaces; legacy records stay unclassified.

Revision ID: 008
Revises: 007
"""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

SCOPED_TABLES = ("projects", "tasks", "memory_entries")


def upgrade():
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "kind IN ('FEDERATION', 'MYWAVE', 'JOINT')", name="ck_workspace_kind"
        ),
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "workspace_id", "principal_id", name="uq_workspace_principal"
        ),
        sa.CheckConstraint(
            "role IN ('reader', 'writer', 'owner')", name="ck_workspace_membership_role"
        ),
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id",
        "workspace_memberships",
        ["workspace_id"],
    )
    for table in SCOPED_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_workspace",
                "workspaces",
                ["workspace_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            batch.create_index(f"ix_{table}_workspace_id", ["workspace_id"])
    # No seed, membership or inference from project names: classification is reviewed.


def downgrade():
    bind = op.get_bind()
    if any(
        bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE workspace_id IS NOT NULL")
        ).scalar_one()
        for table in SCOPED_TABLES
    ):
        raise RuntimeError(
            "Classified records exist; retain schema or use an explicit recovery plan"
        )
    if bind.execute(sa.text("SELECT count(*) FROM workspaces")).scalar_one():
        raise RuntimeError(
            "Workspace data exists; retain schema or use an explicit recovery plan"
        )
    for table in reversed(SCOPED_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_workspace_id")
            batch.drop_constraint(f"fk_{table}_workspace", type_="foreignkey")
            batch.drop_column("workspace_id")
    op.drop_index(
        "ix_workspace_memberships_workspace_id", table_name="workspace_memberships"
    )
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
