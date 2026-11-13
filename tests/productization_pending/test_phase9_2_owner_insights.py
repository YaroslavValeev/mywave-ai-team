from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.storage.models import TaskStatus
from app.storage.repositories import TaskRepository
from app.services.owner_insights import (
    get_weekly_digest,
    get_blockers_summary,
    get_awaiting_decisions_summary,
    get_completed_recently_summary,
    get_rework_signal_summary,
    get_long_running_summary,
)
from app.presenters.owner_insight_presenters import (
    format_weekly_digest,
    format_blockers_summary,
    format_awaiting_decisions_summary,
    format_completed_recently_summary,
    format_project_activity_summary,
    format_rework_signal_summary,
    format_degraded_signal_summary,
    format_long_running_summary,
)


def test_weekly_digest_payload_shape(db_session):
    payload = get_weekly_digest(limit=3)
    assert "completed_count" in payload
    assert "approvals_count" in payload
    assert "rework_count" in payload
    assert "degraded_events_count" in payload
    assert "owner_focus" in payload


def test_blockers_summary_returns_actionable_items(db_session):
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="Need decision")
    repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    data = get_blockers_summary(limit=5)
    assert data["blockers_count"] >= 1
    assert any(i.get("task") and i["task"].id == t.id for i in data["items"])


def test_awaiting_decisions_summary_returns_pending_owner_items(db_session):
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="Approve me")
    repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    data = get_awaiting_decisions_summary(limit=10)
    assert data["pending_count"] >= 1
    assert any(x.id == t.id for x in data["items"])


def test_completed_recently_summary_returns_recent_outputs(db_session):
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="Done task")
    repo.update_task(t.id, status=TaskStatus.DONE.value, summary="ready")
    data = get_completed_recently_summary(limit=10)
    assert data["completed_count"] >= 1
    assert any(x.id == t.id for x in data["items"])


def test_rework_signal_summary_detects_repeated_rework(db_session):
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="Rework task")
    repo.update_task(t.id, status=TaskStatus.REWORK.value, rework_cycles=2)
    data = get_rework_signal_summary(limit=10)
    assert data["count"] >= 1
    assert any(x.id == t.id for x in data["items"])


def test_long_running_summary_detects_stale_items(db_session):
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="Long running")
    repo.update_task(t.id, status=TaskStatus.IN_PIPELINE.value)
    old = datetime.now(timezone.utc) - timedelta(hours=8)
    db_session.query(type(t)).filter_by(id=t.id).update({"updated_at": old})
    db_session.commit()
    data = get_long_running_summary(limit=10)
    assert data["count"] >= 1
    assert any(i.get("task") and i["task"].id == t.id for i in data["items"])


def test_owner_insight_presenters_return_human_readable_messages():
    weekly = format_weekly_digest({"completed_count": 1, "approvals_count": 2, "rework_count": 0, "pending_approvals_count": 1, "blockers_count": 1, "degraded_events_count": 0, "owner_focus": "focus"})
    assert "Weekly" in weekly and "{" not in weekly
    assert "Blockers" in format_blockers_summary({"blockers_count": 0, "items": []})
    assert "Awaiting" in format_awaiting_decisions_summary({"pending_count": 0, "items": []})
    assert "Completed" in format_completed_recently_summary({"completed_count": 0, "artifact_count": 0, "items": []})
    assert "Project" in format_project_activity_summary({"projects_count": 1, "top_projects": [{"project": "x", "tasks_count": 1}]})
    assert "Rework" in format_rework_signal_summary({"count": 0, "items": []})
    assert "Degraded" in format_degraded_signal_summary({"current_state": "OK", "events_count_7d": 0, "events": []})
    assert "Long-running" in format_long_running_summary({"count": 0, "items": []})


def test_owner_insight_commands_are_wired():
    import app.bot.handlers as h
    assert hasattr(h, "handle_owner_digest")
    assert hasattr(h, "handle_owner_blockers")
    assert hasattr(h, "handle_owner_decisions")
    assert hasattr(h, "handle_owner_done")
    assert hasattr(h, "handle_owner_insights")


def test_weekly_digest_scheduler_hook_exists():
    from app.bot.owner_notification_loop import _run_weekly_digest_if_due
    assert callable(_run_weekly_digest_if_due)
