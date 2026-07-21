# app/storage/models.py — SQLAlchemy модели
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TaskStatus(str, Enum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    IN_PIPELINE = "IN_PIPELINE"
    IN_ROUNDTABLE = "IN_ROUNDTABLE"
    IN_COURT = "IN_COURT"
    EXECUTION_READY = "EXECUTION_READY"  # Exploration dry-run: артефакты для Cursor без pipeline/court
    WAIT_OWNER = "WAIT_OWNER"
    APPROVED_WAIT_MERGE = "APPROVED_WAIT_MERGE"  # v0.2: Owner approved, ждём ручной merge
    NEED_INFO = "NEED_INFO"
    REWORK = "REWORK"
    DONE = "DONE"
    ARCHIVED = "ARCHIVED"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    owner_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    project_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # product|event|media|platform
    business_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    monetization_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # idea|validation|build|launch|growth
    revenue_target: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    cost_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_focus_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    owner_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.NEW.value)
    domain: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    task_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    business_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # marketing|product|revenue|ops
    impact_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # low|medium|high
    impact_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    business_action_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    business_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    criticality: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    plan_or_execute: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    rework_cycles: Mapped[int] = mapped_column(Integer, default=0)
    report_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pr_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ci_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    risk_table_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    handoffs: Mapped[list["Handoff"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    runs: Mapped[list["Run"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    execution_events: Mapped[list["ExecutionEvent"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped[Optional["Task"]] = relationship(back_populates="audit_events")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # approve, rework, clarify
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="decisions")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="decision", cascade="all, delete-orphan")


class Run(Base):
    """Персистентный проход оркестрации (SoT для run_id)."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    orchestrator: Mapped[str] = mapped_column(String(64), default="orchestration_runtime")
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phase_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    requested_stop_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="runs")
    execution_events: Mapped[list["ExecutionEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Approval(Base):
    """Явная фиксация approval рядом с Decision (shared-schema)."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    decision_id: Mapped[Optional[int]] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # REQUESTED, APPROVED, REJECTED, EXPIRED
    requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="approvals")
    decision: Mapped[Optional["Decision"]] = relationship(back_populates="approvals")


class ExecutionEvent(Base):
    __tablename__ = "execution_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="execution_events")
    run: Mapped[Optional["Run"]] = relationship(back_populates="execution_events")


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship()


class OwnerProfile(Base):
    """Профиль владельца (MVP: одна строка owner_key=default)."""

    __tablename__ = "owner_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    primary_interface: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    preferred_work_mode: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OwnerMemoryItem(Base):
    """Правила, предпочтения, приоритеты, паттерны владельца (не путать с project memory)."""

    __tablename__ = "owner_memory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False, default="canonical")
    strength: Mapped[float] = mapped_column(Float, default=1.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    priority_rank: Mapped[int] = mapped_column(Integer, default=0)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="global", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    meta_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OwnerOverride(Base):
    """Разовое переопределение правила (valid_until NULL = бессрочно)."""

    __tablename__ = "owner_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    override_text: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    meta_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class Handoff(Base):
    __tablename__ = "handoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    md_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="handoffs")
