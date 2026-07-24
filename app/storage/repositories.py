# app/storage/repositories.py
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine, not_, or_, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Approval,
    AuditEvent,
    Base,
    Decision,
    ExecutionEvent,
    Handoff,
    IntakeDraft,
    MemoryEntry,
    OwnerMemoryItem,
    OwnerOverride,
    OwnerProfile,
    Project,
    Run,
    Task,
    TaskStatus,
)
from .sot_compat import ensure_task_project_linked

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


DEFAULT_PROJECT_SLUG = "default"


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def _ensure_default_project(self) -> Project:
        p = self.session.query(Project).filter(Project.slug == DEFAULT_PROJECT_SLUG).first()
        if p:
            return p
        p = Project(slug=DEFAULT_PROJECT_SLUG, name="Default", status="ACTIVE")
        self.session.add(p)
        self.session.commit()
        self.session.refresh(p)
        return p

    def get_default_project(self) -> Project:
        """Публичная обёртка для Smart Intake / сидов."""
        return self._ensure_default_project()

    def get_project_by_slug(self, slug: str) -> Optional[Project]:
        return self.session.query(Project).filter(Project.slug == slug).first()

    def get_project(self, project_id: int) -> Optional[Project]:
        return self.session.get(Project, project_id)

    def list_active_projects(self, limit: int = 50) -> list[Project]:
        return (
            self.session.query(Project)
            .filter(Project.status == "ACTIVE")
            .order_by(Project.name.asc())
            .limit(limit)
            .all()
        )

    def recent_open_tasks(self, limit: int = 15) -> list[Task]:
        closed = ("DONE", "ARCHIVED")
        return (
            self.session.query(Task)
            .filter(not_(Task.status.in_(closed)))
            .order_by(Task.updated_at.desc())
            .limit(limit)
            .all()
        )

    def list_memory_entries(self, project_id: int, limit: int = 15) -> list[MemoryEntry]:
        return (
            self.session.query(MemoryEntry)
            .filter(MemoryEntry.project_id == project_id)
            .order_by(MemoryEntry.created_at.desc())
            .limit(limit)
            .all()
        )

    def create_task(self, owner_text: str, *, project_id: Optional[int] = None) -> Task:
        pid = project_id
        if pid is None:
            pid = self._ensure_default_project().id
        task = Task(owner_text=owner_text, status=TaskStatus.NEW.value, project_id=pid)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        task = self.session.get(Task, task_id)
        if task is None:
            return None
        return ensure_task_project_linked(self.session, task)

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
        pr_url: Optional[str] = None,
        commit_sha: Optional[str] = None,
        ci_url: Optional[str] = None,
        business_type: Optional[str] = None,
        impact_level: Optional[str] = None,
        impact_score: Optional[float] = None,
        business_action_json: Optional[dict] = None,
        business_outcome: Optional[str] = None,
    ) -> Optional[Task]:
        from sqlalchemy import update as sa_update
        from sqlalchemy.orm.attributes import flag_modified
        from sqlalchemy.orm.exc import StaleDataError

        task = self.get_task(task_id)
        if not task:
            return None

        values: dict = {}
        if status is not None:
            task.status = status
            values["status"] = status
        if domain is not None:
            task.domain = domain
            values["domain"] = domain
        if task_type is not None:
            task.task_type = task_type
            values["task_type"] = task_type
        if criticality is not None:
            task.criticality = criticality
            values["criticality"] = criticality
        if plan_or_execute is not None:
            task.plan_or_execute = plan_or_execute
            values["plan_or_execute"] = plan_or_execute
        if report_path is not None:
            task.report_path = report_path
            values["report_path"] = report_path
        if summary is not None:
            task.summary = summary
            values["summary"] = summary
        if risk_table_json is not None:
            task.risk_table_json = dict(risk_table_json)
            flag_modified(task, "risk_table_json")
            values["risk_table_json"] = dict(risk_table_json)
        if rework_cycles is not None:
            task.rework_cycles = rework_cycles
            values["rework_cycles"] = rework_cycles
        if pr_url is not None:
            task.pr_url = pr_url
            values["pr_url"] = pr_url
        if commit_sha is not None:
            task.commit_sha = commit_sha
            values["commit_sha"] = commit_sha
        if ci_url is not None:
            task.ci_url = ci_url
            values["ci_url"] = ci_url
        if business_type is not None:
            task.business_type = business_type
            values["business_type"] = business_type
        if impact_level is not None:
            task.impact_level = impact_level
            values["impact_level"] = impact_level
        if impact_score is not None:
            task.impact_score = impact_score
            values["impact_score"] = impact_score
        if business_action_json is not None:
            payload = dict(business_action_json)
            task.business_action_json = payload
            flag_modified(task, "business_action_json")
            values["business_action_json"] = payload
        if business_outcome is not None:
            task.business_outcome = business_outcome
            values["business_outcome"] = business_outcome

        if not values:
            return task

        values["updated_at"] = datetime.utcnow()
        task.updated_at = values["updated_at"]

        try:
            self.session.commit()
        except StaleDataError:
            # Some drivers report rowcount=-1 → ORM StaleDataError even when UPDATE succeeded.
            self.session.rollback()
            self.session.execute(sa_update(Task).where(Task.id == task_id).values(**values))
            self.session.commit()
        task = self.get_task(task_id)
        return task

    def append_owner_context(self, task_id: int, block: str) -> Optional[Task]:
        """Дописать блок к owner_text (Smart Intake attach) и сохранить."""
        task = self.get_task(task_id)
        if not task:
            return None
        block = (block or "").strip()
        if not block:
            return task
        sep = "\n\n--- Smart Intake attach ---\n\n"
        existing = (task.owner_text or "").rstrip()
        task.owner_text = existing + sep + block if existing else block
        self.session.commit()
        self.session.refresh(task)
        return task

    def add_audit_event(self, event_type: str, task_id: Optional[int] = None, payload: Optional[dict] = None):
        ev = AuditEvent(task_id=task_id, event_type=event_type, payload_json=payload)
        self.session.add(ev)
        self.session.commit()

    def get_open_pending_approval(self, task_id: int) -> Optional[Approval]:
        return (
            self.session.query(Approval)
            .filter(Approval.task_id == task_id, Approval.status == "REQUESTED")
            .order_by(Approval.id.desc())
            .first()
        )

    def ensure_pending_owner_approval(self, task_id: int) -> Approval:
        existing = self.get_open_pending_approval(task_id)
        if existing:
            return existing
        now = datetime.utcnow()
        ap = Approval(
            task_id=task_id,
            decision_id=None,
            required=True,
            status="REQUESTED",
            requested_at=now,
        )
        self.session.add(ap)
        self.session.commit()
        self.session.refresh(ap)
        return ap

    def add_decision(self, task_id: int, decision: str, rationale: Optional[str] = None, owner_approval: bool = False) -> Decision:
        d = Decision(task_id=task_id, decision=decision, rationale=rationale, owner_approval=owner_approval)
        self.session.add(d)
        self.session.commit()
        self.session.refresh(d)
        pending = self.get_open_pending_approval(task_id)
        now = datetime.utcnow()

        if owner_approval:
            if pending:
                pending.decision_id = d.id
                pending.status = "APPROVED"
                pending.resolved_at = now
                pending.resolved_by = "owner"
                self.session.add(pending)
                self.session.commit()
            else:
                ap = Approval(
                    task_id=task_id,
                    decision_id=d.id,
                    required=True,
                    status="APPROVED",
                    requested_at=d.created_at,
                    resolved_at=now,
                    resolved_by="owner",
                )
                self.session.add(ap)
                self.session.commit()
            return d

        if pending and decision in {"r", "c"}:
            pending.decision_id = d.id
            pending.status = "REJECTED"
            pending.resolved_at = now
            pending.resolved_by = "owner"
            self.session.add(pending)
            self.session.commit()
        return d

    def add_handoff(self, task_id: int, step_index: int, step_name: str, payload: dict, md_path: Optional[str] = None):
        h = Handoff(task_id=task_id, step_index=step_index, step_name=step_name, payload_json=payload, md_path=md_path)
        self.session.add(h)
        self.session.commit()

    def create_run_record(
        self,
        *,
        task_id: int,
        run_id: str,
        source: Optional[str],
        state: str,
        phase: Optional[str],
        phase_label: Optional[str],
        message: Optional[str],
        current_step: Optional[str],
        started_at: Optional[datetime],
        is_active: bool = True,
        orchestrator: str = "orchestration_runtime",
    ) -> Run:
        run = Run(
            run_id=run_id,
            task_id=task_id,
            orchestrator=orchestrator,
            source=source,
            state=state,
            phase=phase,
            phase_label=phase_label,
            message=message,
            current_step=current_step,
            started_at=started_at,
            is_active=is_active,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def update_run_terminal(
        self,
        run_id: str,
        *,
        state: str,
        phase: Optional[str],
        phase_label: Optional[str],
        message: Optional[str],
        current_step: Optional[str],
        finished_at: Optional[datetime],
        requested_stop_at: Optional[datetime],
        last_error: Optional[str],
        result_status: Optional[str],
        is_active: bool,
    ) -> Optional[Run]:
        run = self.session.query(Run).filter(Run.run_id == run_id).first()
        if not run:
            return None
        run.state = state
        run.phase = phase
        run.phase_label = phase_label
        run.message = message
        run.current_step = current_step
        run.finished_at = finished_at
        run.requested_stop_at = requested_stop_at
        run.last_error = last_error
        run.result_status = result_status
        run.is_active = is_active
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run_by_run_id(self, run_id: str) -> Optional[Run]:
        return self.session.query(Run).filter(Run.run_id == run_id).first()

    def list_runs_for_task(self, task_id: int, limit: int = 50) -> list[Run]:
        return (
            self.session.query(Run)
            .filter(Run.task_id == task_id)
            .order_by(Run.id.desc())
            .limit(limit)
            .all()
        )

    def list_execution_events_for_task(self, task_id: int, limit: int = 100) -> list[ExecutionEvent]:
        return (
            self.session.query(ExecutionEvent)
            .filter(ExecutionEvent.task_id == task_id)
            .order_by(ExecutionEvent.id.desc())
            .limit(limit)
            .all()
        )

    def add_execution_event(
        self,
        task_id: int,
        *,
        run_db_id: Optional[int],
        event_type: str,
        phase: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> ExecutionEvent:
        ev = ExecutionEvent(
            task_id=task_id,
            run_id=run_db_id,
            event_type=event_type,
            phase=phase,
            payload_json=payload,
        )
        self.session.add(ev)
        self.session.commit()
        self.session.refresh(ev)
        return ev

    def add_memory_entry(
        self,
        *,
        project_id: int,
        scope: str,
        content: str,
        task_id: Optional[int] = None,
        source_ref: Optional[str] = None,
    ) -> MemoryEntry:
        mem = MemoryEntry(
            project_id=project_id,
            task_id=task_id,
            scope=scope,
            content=content,
            source_ref=source_ref,
        )
        self.session.add(mem)
        self.session.commit()
        self.session.refresh(mem)
        return mem

    # --- Owner Memory / Rules Layer ---

    def get_owner_profile(self, owner_key: str = "default") -> Optional[OwnerProfile]:
        return self.session.query(OwnerProfile).filter(OwnerProfile.owner_key == owner_key).first()

    def list_owner_memory_items(
        self,
        owner_key: str = "default",
        *,
        kind: Optional[str] = None,
        scope: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        active_only: bool = True,
        tiers: Optional[list[str]] = None,
    ) -> list[OwnerMemoryItem]:
        q = self.session.query(OwnerMemoryItem).filter(OwnerMemoryItem.owner_key == owner_key)
        if active_only:
            q = q.filter(OwnerMemoryItem.is_active.is_(True))
        if kind:
            q = q.filter(OwnerMemoryItem.kind == kind)
        if scope:
            q = q.filter((OwnerMemoryItem.scope == scope) | (OwnerMemoryItem.scope == "global"))
        elif scopes:
            q = q.filter(
                or_(OwnerMemoryItem.scope == "global", OwnerMemoryItem.scope.in_(scopes))
            )
        if tiers:
            q = q.filter(OwnerMemoryItem.tier.in_(tiers))
        return q.order_by(OwnerMemoryItem.priority_rank.asc(), OwnerMemoryItem.id.asc()).all()

    def list_valid_owner_overrides(
        self,
        owner_key: str,
        target_scope: str,
        target_id: str,
    ) -> list[OwnerOverride]:
        from datetime import datetime as dt

        now = dt.utcnow()
        rows = (
            self.session.query(OwnerOverride)
            .filter(
                OwnerOverride.owner_key == owner_key,
                OwnerOverride.target_scope == target_scope,
                OwnerOverride.target_id == target_id,
            )
            .all()
        )
        return [o for o in rows if o.valid_until is None or o.valid_until > now]

    def count_owner_memory_items(self, owner_key: str = "default") -> int:
        return (
            self.session.query(OwnerMemoryItem)
            .filter(OwnerMemoryItem.owner_key == owner_key)
            .count()
        )

    def add_owner_memory_item(
        self,
        *,
        owner_key: str,
        kind: str,
        item_key: str,
        text: str,
        tier: str = "inferred",
        scope: str = "global",
        strength: float = 0.5,
        weight: float = 0.5,
        priority_rank: int = 50,
        is_active: bool = True,
        is_confirmed: bool = False,
        meta_json: Optional[dict] = None,
    ) -> OwnerMemoryItem:
        row = OwnerMemoryItem(
            owner_key=owner_key,
            kind=kind,
            item_key=item_key,
            text=text,
            tier=tier,
            strength=strength,
            weight=weight,
            priority_rank=priority_rank,
            scope=scope,
            is_active=is_active,
            is_confirmed=is_confirmed,
            meta_json=meta_json,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_owner_override(
        self,
        *,
        owner_key: str,
        target_scope: str,
        target_id: str,
        override_text: str,
        valid_until: Optional[datetime] = None,
        meta_json: Optional[dict] = None,
    ) -> OwnerOverride:
        row = OwnerOverride(
            owner_key=owner_key,
            target_scope=target_scope,
            target_id=target_id,
            override_text=override_text,
            valid_until=valid_until,
            meta_json=meta_json,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def _get_intake_draft_row(self, draft_id: str) -> Optional[IntakeDraft]:
        row = self.session.query(IntakeDraft).filter(IntakeDraft.draft_id == draft_id).first()
        if not row:
            return None
        if row.expires_at < datetime.utcnow():
            self.session.delete(row)
            self.session.commit()
            return None
        return row

    def put_intake_draft(self, payload: dict, ttl_sec: int = 900) -> str:
        """Сохранить черновик Smart Intake (кнопки Confirm/Attach) в БД."""
        draft_id = uuid.uuid4().hex[:8]
        row = IntakeDraft(
            draft_id=draft_id,
            payload_json=payload,
            expires_at=datetime.utcnow() + timedelta(seconds=max(60, int(ttl_sec))),
        )
        self.session.add(row)
        self.session.commit()
        return draft_id

    def peek_intake_draft(self, draft_id: str) -> Optional[dict]:
        row = self._get_intake_draft_row(draft_id)
        return dict(row.payload_json) if row else None

    def pop_intake_draft(self, draft_id: str) -> Optional[dict]:
        row = self._get_intake_draft_row(draft_id)
        if not row:
            return None
        payload = dict(row.payload_json)
        self.session.delete(row)
        self.session.commit()
        return payload

    def purge_expired_intake_drafts(self) -> int:
        now = datetime.utcnow()
        rows = self.session.query(IntakeDraft).filter(IntakeDraft.expires_at < now).all()
        for row in rows:
            self.session.delete(row)
        if rows:
            self.session.commit()
        return len(rows)
