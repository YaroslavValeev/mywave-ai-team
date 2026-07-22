"""Business Layer fields for Project/Task (Phase v1)

Revision ID: 006
Revises: 005
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns(table)}
    if column.name not in cols:
        op.add_column(table, column)


def upgrade() -> None:
    # projects
    _add_column_if_missing("projects", sa.Column("project_type", sa.String(length=32), nullable=True))
    _add_column_if_missing("projects", sa.Column("business_goal", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("monetization_model", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("stage", sa.String(length=32), nullable=True))
    _add_column_if_missing("projects", sa.Column("revenue_target", sa.String(length=128), nullable=True))
    _add_column_if_missing("projects", sa.Column("cost_model", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("owner_focus_level", sa.String(length=32), nullable=True))

    # tasks
    _add_column_if_missing("tasks", sa.Column("business_type", sa.String(length=32), nullable=True))
    _add_column_if_missing("tasks", sa.Column("impact_level", sa.String(length=16), nullable=True))
    _add_column_if_missing("tasks", sa.Column("impact_score", sa.Float(), nullable=True))
    _add_column_if_missing("tasks", sa.Column("business_action_json", sa.JSON(), nullable=True))
    _add_column_if_missing("tasks", sa.Column("business_outcome", sa.Text(), nullable=True))


def downgrade() -> None:
    # Осознанно no-op для безопасной обратной совместимости исторических данных.
    pass

