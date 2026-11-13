# app/services/owner_notifications.py — Phase 9.1: build payloads and should_send for owner notifications
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_owner_notification_config
from app.owner_summary import build_detailed_summary
from app.services.owner_insights import get_weekly_digest
from app.services.owner_recommendations import get_strategic_weekly_digest, get_monthly_digest_baseline
from app.services.owner_portfolio import get_portfolio_digest
from app.services.notification_state import (
    should_send_degraded_alert,
    should_send_recovered_alert,
    should_send_daily_summary,
    should_send_weekly_digest,
    should_send_monthly_digest,
    should_send_stuck_task_alert as state_should_send_stuck,
)
from app.storage.repositories import get_session_factory, TaskRepository
from app.storage.models import TaskStatus


def build_daily_summary_payload(tasks_limit: int = 5, approvals_limit: int = 5, artifacts_limit: int = 5) -> dict[str, Any]:
    """Payload для daily summary: сводка + топ задач/approvals/artifacts."""
    return build_detailed_summary(
        tasks_limit=tasks_limit,
        approvals_limit=approvals_limit,
        artifacts_limit=artifacts_limit,
    )


def build_weekly_digest_payload(limit: int = 5) -> dict[str, Any]:
    """Payload для weekly managerial digest."""
    return get_weekly_digest(limit=limit)


def build_strategic_weekly_digest_payload() -> dict[str, Any]:
    """Payload для стратегической недельной сводки (Phase 9.3)."""
    return get_strategic_weekly_digest()


def build_monthly_digest_payload() -> dict[str, Any]:
    """Payload для месячной сводки (last 30 days)."""
    return get_monthly_digest_baseline()


def build_portfolio_weekly_digest_payload(window_days: int = 7) -> dict[str, Any]:
    """Payload для portfolio weekly digest (Phase 9.6): cross-project view за окно."""
    return get_portfolio_digest(window_days=window_days)


def build_approval_alert(task_id: int, summary: Optional[str] = None) -> dict[str, Any]:
    return {"task_id": task_id, "summary": (summary or "")[:300]}


def build_completion_alert(task_id: int, summary: Optional[str] = None, report_path: Optional[str] = None) -> dict[str, Any]:
    return {"task_id": task_id, "summary": (summary or "")[:300], "report_path": report_path}


def build_artifact_ready_alert(task_id: int, report_path: str, title: Optional[str] = None) -> dict[str, Any]:
    return {"task_id": task_id, "report_path": report_path, "title": title or f"Task #{task_id} report"}


def build_degraded_alert(reason: Optional[str] = None, molt_message: Optional[str] = None) -> dict[str, Any]:
    return {"reason": reason or "Molt/runtime unavailable", "molt_message": molt_message or "down"}


def build_recovered_alert() -> dict[str, Any]:
    return {}


def build_stuck_task_alert(task_id: int, status: str, threshold_minutes: Optional[int] = None) -> dict[str, Any]:
    return {"task_id": task_id, "status": status, "threshold_minutes": threshold_minutes}


# --- Orchestration-level: should we send? (respects config + notification_state) ---


def should_send_degraded_alert_now() -> bool:
    cfg = get_owner_notification_config()
    if not cfg.get("degraded_alerts_enabled", True):
        return False
    return should_send_degraded_alert()


def should_send_recovered_alert_now() -> bool:
    cfg = get_owner_notification_config()
    if not cfg.get("recovery_alerts_enabled", True):
        return False
    return should_send_recovered_alert()


def should_send_daily_summary_now() -> bool:
    cfg = get_owner_notification_config()
    if not cfg.get("daily_summary_enabled", True):
        return False
    return should_send_daily_summary()


def should_send_stuck_task_alert(task_id: int) -> bool:
    cfg = get_owner_notification_config()
    if not cfg.get("stuck_task_alerts_enabled", True):
        return False
    cooldown = cfg.get("stuck_alert_cooldown_minutes", 1440)
    return state_should_send_stuck(task_id, cooldown_minutes=cooldown)


def should_send_weekly_digest_now() -> bool:
    cfg = get_owner_notification_config()
    if not cfg.get("weekly_digest_enabled", True):
        return False
    return should_send_weekly_digest()


def should_send_monthly_digest_now() -> bool:
    cfg = get_owner_notification_config()
    if not cfg.get("monthly_digest_enabled", True):
        return False
    return should_send_monthly_digest()


def get_stuck_tasks() -> list[dict[str, Any]]:
    """Задачи, подпадающие под STUCK_TASK_POLICY (waiting approval или no progress)."""
    cfg = get_owner_notification_config()
    wait_mins = cfg.get("stuck_waiting_approval_minutes", 1440)
    no_progress_mins = cfg.get("stuck_no_progress_minutes", 360)
    now = datetime.now(timezone.utc)
    result = []

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()

    waiting_statuses = (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)
    progress_statuses = (TaskStatus.IN_PIPELINE.value, TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value)

    for t in tasks:
        updated = t.updated_at or t.created_at
        if not updated:
            continue
        if getattr(updated, "tzinfo", None) is None:
            updated = updated.replace(tzinfo=timezone.utc)
        delta_minutes = (now - updated).total_seconds() / 60
        if t.status in waiting_statuses and delta_minutes >= wait_mins:
            result.append({"task": t, "reason": "waiting_approval", "threshold_minutes": wait_mins})
        elif t.status in progress_statuses and delta_minutes >= no_progress_mins:
            result.append({"task": t, "reason": "no_progress", "threshold_minutes": no_progress_mins})
    return result
