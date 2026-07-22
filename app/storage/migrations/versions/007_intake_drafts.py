"""Persistent Smart Intake drafts (survive bot restart)

Revision ID: 007
Revises: 006
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "intake_drafts" in insp.get_table_names():
        return
    op.create_table(
        "intake_drafts",
        sa.Column("draft_id", sa.String(length=8), primary_key=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_intake_drafts_expires_at", "intake_drafts", ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "intake_drafts" not in insp.get_table_names():
        return
    op.drop_index("ix_intake_drafts_expires_at", table_name="intake_drafts")
    op.drop_table("intake_drafts")
