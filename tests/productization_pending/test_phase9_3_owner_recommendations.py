# tests/test_phase9_3_owner_recommendations.py — Phase 9.3: strategic digests and owner recommendations
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.storage.models import TaskStatus
from app.storage.repositories import TaskRepository
from app.services.owner_recommendations import (
    get_next_actions,
    get_decision_queue,
    get_project_health_summary,
    get_priority_signals,
    get_risk_signals,
    get_strategic_weekly_digest,
    get_monthly_digest_baseline,
)
from app.presenters.owner_recommendation_presenters import (
    format_next_actions,
    format_decision_queue,
    format_project_health_summary,
    format_priority_signals,
    format_risk_signals,
    format_strategic_weekly_digest,
    format_monthly_digest_baseline,
)


def test_next_actions_returns_prioritised_items(db_session):
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="Need approval")
    repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    data = get_next_actions(limit=5)
    assert "items" in data
    assert "count" in data
    assert isinstance(data["items"], list)
    assert data["count"] >= 1
    for a in data["items"]:
        assert "action_type" in a
        assert "reason" in a
        assert "priority" in a
        assert "suggested_action" in a


def test_decision_queue_contains_pending_owner_items(db_session):
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="Approve me")
    repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    data = get_decision_queue(limit=10)
    assert "items" in data
    assert "count" in data
    for q in data["items"]:
        assert "reason" in q
        assert "priority" in q
        assert "suggested_next_action" in q
        assert "if_ignored" in q


def test_project_health_summary_returns_grouped_statuses(db_session):
    data = get_project_health_summary(limit=10)
    assert "items" in data
    assert "count" in data
    for h in data["items"]:
        assert h["status"] in ("healthy", "attention_needed", "critical")
        assert "project" in h
        assert "reason" in h


def test_risk_signals_include_explainable_reasons(db_session):
    data = get_risk_signals(limit=5)
    assert "items" in data
    for r in data["items"]:
        assert "reason" in r
        assert "why_it_matters" in r or "suggested_action" in r


def test_strategic_weekly_digest_payload_shape(db_session):
    payload = get_strategic_weekly_digest()
    assert "window_days" in payload
    assert payload["window_days"] == 7
    assert "completed_count" in payload
    assert "key_risks" in payload
    assert "needs_decision" in payload
    assert "next_week_priorities" in payload
    assert "owner_focus" in payload


def test_monthly_digest_baseline_shape(db_session):
    payload = get_monthly_digest_baseline()
    assert "window_days" in payload
    assert payload["window_days"] == 30
    assert "completed_count" in payload
    assert "active_count" in payload
    assert "pending_approvals_count" in payload
    assert "top_recommendations" in payload


def test_recommendation_presenters_return_human_readable_messages():
    next_data = {"items": [{"action_type": "approval", "task_id": 1, "reason": "Pending", "priority": "high", "suggested_action": "Approve", "if_deferred": None}], "count": 1}
    msg = format_next_actions(next_data)
    assert "Next" in msg or "next" in msg.lower() or "approval" in msg.lower() or "Pending" in msg
    assert "{" not in msg

    queue_data = {"items": [{"task_id": 1, "reason": "Pending approval", "priority": "high", "suggested_next_action": "Approve", "if_ignored": "Backlog"}], "count": 1}
    msg = format_decision_queue(queue_data)
    assert "Decision" in msg or "decision" in msg.lower() or "Pending" in msg
    assert "{" not in msg

    health_data = {"items": [{"project": "general", "status": "healthy", "reason": "OK", "active_count": 0, "pending_count": 0}], "count": 1}
    msg = format_project_health_summary(health_data)
    assert "health" in msg.lower() or "healthy" in msg.lower() or "project" in msg.lower()
    assert "{" not in msg

    risk_data = {"items": [{"risk_type": "degraded", "reason": "Runtime down", "why_it_matters": "Risk", "suggested_action": "Check"}]}
    msg = format_risk_signals(risk_data)
    assert "risk" in msg.lower() or "Risk" in msg or "reason" in msg.lower()
    assert "{" not in msg

    weekly_data = {"window_days": 7, "completed_count": 0, "key_risks": [], "owner_focus": "focus", "next_week_priorities": []}
    msg = format_strategic_weekly_digest(weekly_data)
    assert "Weekly" in msg or "weekly" in msg.lower() or "strategic" in msg.lower()
    assert "{" not in msg

    monthly_data = {"window_days": 30, "completed_count": 0, "active_count": 0, "pending_approvals_count": 0, "top_recommendations": []}
    msg = format_monthly_digest_baseline(monthly_data)
    assert "Monthly" in msg or "monthly" in msg.lower() or "30" in msg
    assert "{" not in msg


def test_owner_recommendation_commands_are_wired():
    import app.bot.handlers as h
    assert hasattr(h, "handle_owner_next")
    assert hasattr(h, "handle_owner_decisions_queue")
    assert hasattr(h, "handle_owner_health_projects")
    assert hasattr(h, "handle_owner_risks")
    assert hasattr(h, "handle_owner_weekly_digest")
    assert hasattr(h, "handle_owner_monthly_digest")


def test_weekly_and_monthly_digest_scheduler_hooks_exist():
    from app.bot.owner_notification_loop import _run_weekly_digest_if_due, _run_monthly_digest_if_due
    assert callable(_run_weekly_digest_if_due)
    assert callable(_run_monthly_digest_if_due)
