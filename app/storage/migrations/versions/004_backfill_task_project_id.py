"""Backfill tasks.project_id to default project (Phase 3 adapter / SoT)

Revision ID: 004
Revises: 003
Create Date: 2026-04-07

"""
from alembic import op
from sqlalchemy import text

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        ts = "datetime('now')"
    else:
        ts = "CURRENT_TIMESTAMP"

    bind.execute(
        text(
            f"""
            INSERT INTO projects (slug, name, status, created_at, updated_at)
            SELECT 'default', 'Default', 'ACTIVE', {ts}, {ts}
            WHERE NOT EXISTS (SELECT 1 FROM projects WHERE slug = 'default')
            """
        )
    )
    bind.execute(
        text(
            """
            UPDATE tasks
            SET project_id = (SELECT id FROM projects WHERE slug = 'default' LIMIT 1)
            WHERE project_id IS NULL
            """
        )
    )


def downgrade() -> None:
    # Не откатываем привязку задач к проекту — только no-op для целостности ревизий.
    pass
