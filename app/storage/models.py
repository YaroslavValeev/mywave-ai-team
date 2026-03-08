# app/storage/models.py — SQLAlchemy модели
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TaskStatus(str, Enum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    IN_PIPELINE = "IN_PIPELINE"
    IN_ROUNDTABLE = "IN_ROUNDTABLE"
    IN_COURT = "IN_COURT"
    WAIT_OWNER = "WAIT_OWNER"
    APPROVED_WAIT_MERGE = "APPROVED_WAIT_MERGE"  # v0.2: Owner approved, ждём ручной merge
    NEED_INFO = "NEED_INFO"
    REWORK = "REWORK"
    DONE = "DONE"
    ARCHIVED = "ARCHIVED"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.NEW.value)
    domain: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    task_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
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

    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    handoffs: Mapped[list["Handoff"]] = relationship(back_populates="task", cascade="all, delete-orphan")


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
