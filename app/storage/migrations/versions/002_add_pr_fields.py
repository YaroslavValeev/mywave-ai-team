"""Add pr_url, commit_sha, ci_url to tasks (v0.2)

Revision ID: 002
Revises: 001
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("pr_url", sa.String(512), nullable=True))
    op.add_column("tasks", sa.Column("commit_sha", sa.String(64), nullable=True))
    op.add_column("tasks", sa.Column("ci_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "ci_url")
    op.drop_column("tasks", "commit_sha")
    op.drop_column("tasks", "pr_url")
