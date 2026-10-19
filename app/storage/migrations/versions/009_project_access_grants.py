"""Explicit product grants; no implicit access from workspace membership.

Revision ID: 009
Revises: 008
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_access_grants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("project_id", "principal_id", name="uq_project_principal"),
        sa.CheckConstraint(
            "role IN ('reader', 'writer', 'owner')", name="ck_project_access_role"
        ),
    )
    op.create_index(
        "ix_project_access_grants_project_id", "project_access_grants", ["project_id"]
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM project_access_grants"))
        .scalar_one()
    ):
        raise RuntimeError(
            "Project grants exist; retain schema or use an explicit recovery plan"
        )
    op.drop_index(
        "ix_project_access_grants_project_id", table_name="project_access_grants"
    )
    op.drop_table("project_access_grants")
