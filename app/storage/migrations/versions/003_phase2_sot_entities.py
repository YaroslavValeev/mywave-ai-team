"""Phase 2: Project, Run, Approval, ExecutionEvent, MemoryEntry; Task.project_id

Revision ID: 003
Revises: 002
Create Date: 2026-04-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def _ensure_index(table: str, name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    existing = {ix["name"] for ix in inspect(bind).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, unique=False)


def upgrade() -> None:
    bind = op.get_bind()

    if not inspect(bind).has_table("projects"):
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(128), nullable=False),
            sa.Column("name", sa.String(256), nullable=False),
            sa.Column("status", sa.String(32), nullable=True),
            sa.Column("owner_id", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )

    if not inspect(bind).has_table("runs"):
        op.create_table(
            "runs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.String(64), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("orchestrator", sa.String(64), nullable=True),
            sa.Column("source", sa.String(64), nullable=True),
            sa.Column("state", sa.String(32), nullable=False),
            sa.Column("phase", sa.String(64), nullable=True),
            sa.Column("phase_label", sa.String(128), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("current_step", sa.String(128), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("requested_stop_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("result_status", sa.String(64), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id"),
        )
    _ensure_index("runs", "ix_runs_task_id", ["task_id"])

    if not inspect(bind).has_table("approvals"):
        op.create_table(
            "approvals",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("decision_id", sa.Integer(), nullable=True),
            sa.Column("required", sa.Boolean(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("requested_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("approvals", "ix_approvals_task_id", ["task_id"])

    if not inspect(bind).has_table("execution_events"):
        op.create_table(
            "execution_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("phase", sa.String(64), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("execution_events", "ix_execution_events_task_id", ["task_id"])
    _ensure_index("execution_events", "ix_execution_events_run_id", ["run_id"])

    if not inspect(bind).has_table("memory_entries"):
        op.create_table(
            "memory_entries",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=True),
            sa.Column("scope", sa.String(64), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source_ref", sa.String(512), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("memory_entries", "ix_memory_entries_project_id", ["project_id"])
    _ensure_index("memory_entries", "ix_memory_entries_task_id", ["task_id"])

    insp = inspect(bind)
    tcols = {c["name"] for c in insp.get_columns("tasks")}
    if "project_id" not in tcols:
        op.add_column("tasks", sa.Column("project_id", sa.Integer(), nullable=True))

    insp = inspect(bind)
    tcols = {c["name"] for c in insp.get_columns("tasks")}
    if "project_id" in tcols:
        fks = {fk["name"] for fk in insp.get_foreign_keys("tasks") if fk.get("name")}
        if "fk_tasks_project_id_projects" not in fks:
            op.create_foreign_key(
                "fk_tasks_project_id_projects",
                "tasks",
                "projects",
                ["project_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_project_id_projects", "tasks", type_="foreignkey")
    op.drop_column("tasks", "project_id")
    op.drop_table("memory_entries")
    op.drop_table("execution_events")
    op.drop_table("approvals")
    op.drop_index("ix_runs_task_id", table_name="runs")
    op.drop_table("runs")
    op.drop_table("projects")
