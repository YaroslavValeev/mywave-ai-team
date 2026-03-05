# app/storage/repositories.py
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Task, AuditEvent, Decision, Handoff, TaskStatus

_engine = None
_session_factory = None


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if url and "asyncpg" in url:
        url = url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    if not url or url in ("postgresql+psycopg2://", "postgresql://"):
        user = os.getenv("POSTGRES_USER", "mywave")
        pwd = os.getenv("POSTGRES_PASSWORD", "mywave")
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "mywave_ai")
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    return url


def get_engine():
    global _engine
    if _engine is None:
        url = get_database_url()
        opts = {"echo": os.getenv("SQL_ECHO", "").lower() == "true"}
        if url.startswith("sqlite"):
            opts["connect_args"] = {"check_same_thread": False}
            opts["poolclass"] = StaticPool
        _engine = create_engine(url, **opts)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            get_engine(), autocommit=False, autoflush=False, class_=Session
        )
    return _session_factory


def init_db(engine=None):
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_task(self, owner_text: str) -> Task:
        task = Task(owner_text=owner_text, status=TaskStatus.NEW.value)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        return self.session.get(Task, task_id)

    def get_all_tasks(self):
        return self.session.query(Task).order_by(Task.created_at.desc()).all()

    def update_task(
        self,
        task_id: int,
        *,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        task_type: Optional[str] = None,
        criticality: Optional[str] = None,
        plan_or_execute: Optional[str] = None,
        report_path: Optional[str] = None,
        summary: Optional[str] = None,
        risk_table_json: Optional[dict] = None,
        rework_cycles: Optional[int] = None,
    ) -> Optional[Task]:
        task = self.get_task(task_id)
        if not task:
            return None
        if status is not None:
            task.status = status
        if domain is not None:
            task.domain = domain
        if task_type is not None:
            task.task_type = task_type
        if criticality is not None:
            task.criticality = criticality
        if plan_or_execute is not None:
            task.plan_or_execute = plan_or_execute
        if report_path is not None:
            task.report_path = report_path
        if summary is not None:
            task.summary = summary
        if risk_table_json is not None:
            task.risk_table_json = risk_table_json
        if rework_cycles is not None:
            task.rework_cycles = rework_cycles
        self.session.commit()
        self.session.refresh(task)
        return task

    def add_audit_event(self, event_type: str, task_id: Optional[int] = None, payload: Optional[dict] = None):
        ev = AuditEvent(task_id=task_id, event_type=event_type, payload_json=payload)
        self.session.add(ev)
        self.session.commit()

    def add_decision(self, task_id: int, decision: str, rationale: Optional[str] = None, owner_approval: bool = False):
        d = Decision(task_id=task_id, decision=decision, rationale=rationale, owner_approval=owner_approval)
        self.session.add(d)
        self.session.commit()

    def add_handoff(self, task_id: int, step_index: int, step_name: str, payload: dict, md_path: Optional[str] = None):
        h = Handoff(task_id=task_id, step_index=step_index, step_name=step_name, payload_json=payload, md_path=md_path)
        self.session.add(h)
        self.session.commit()
