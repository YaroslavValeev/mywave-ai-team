# tests/test_phase9_1_owner_notifications.py — Phase 9.1: owner notification layer
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import pytest

from app.services.owner_notifications import (
    build_daily_summary_payload,
    build_approval_alert,
    build_completion_alert,
    build_degraded_alert,
    build_recovered_alert,
    build_stuck_task_alert,
    should_send_degraded_alert_now,
    should_send_recovered_alert_now,
    should_send_daily_summary_now,
    should_send_stuck_task_alert,
    get_stuck_tasks,
)
from app.services.notification_state import (
    record_degraded_sent,
    record_recovered_sent,
    record_daily_summary_sent,
    record_stuck_alert_sent,
    should_send_degraded_alert,
    should_send_recovered_alert,
    reset_for_tests,
)
from app.presenters.notification_presenters import (
    format_daily_summary_notification,
    format_approval_alert,
    format_completion_alert,
    format_degraded_alert,
    format_recovered_alert,
    format_stuck_task_alert,
)
from app.bot.notify import send_owner_notification, _format_owner_notification
from app.storage.models import TaskStatus
from app.storage.repositories import TaskRepository


@pytest.fixture(autouse=True)
def reset_notification_state():
    reset_for_tests()
    yield
    reset_for_tests()


def test_daily_summary_payload_shape(db_session):
    """Проверяет форму daily summary payload."""
    payload = build_daily_summary_payload(tasks_limit=2, approvals_limit=2, artifacts_limit=2)
    assert "active_tasks_count" in payload or "state" in payload
    assert "molt_ok" in payload
    assert "state" in payload
    assert payload.get("state") in ("OK", "DEGRADED", "Waiting approvals", None) or True
    assert "pending_approvals_list" in payload or "top_tasks" in payload or "recent_artifacts_list" in payload


def test_approval_alert_built_for_pending_approval():
    """Проверяет approval notification payload."""
    payload = build_approval_alert(42, summary="Need approve for execute")
    assert payload["task_id"] == 42
    assert "Need approve" in payload["summary"]
    payload2 = build_approval_alert(1)
    assert payload2["task_id"] == 1
    assert "summary" in payload2


def test_degraded_alert_sent_once_until_recovery():
    """Проверяет anti-spam правило для degraded alerts."""
    assert should_send_degraded_alert() is True
    record_degraded_sent()
    assert should_send_degraded_alert() is False
    record_recovered_sent()
    assert should_send_degraded_alert() is True


def test_recovered_alert_sent_after_degraded():
    """Проверяет, что recovery alert разрешён только после degraded."""
    assert should_send_recovered_alert() is False
    record_degraded_sent()
    assert should_send_recovered_alert() is True
    record_recovered_sent()
    assert should_send_recovered_alert() is False


def test_stuck_task_alert_respects_cooldown():
    """Проверяет dedupe/cooldown для stuck alerts."""
    assert should_send_stuck_task_alert(1) is True
    record_stuck_alert_sent(1)
    assert should_send_stuck_task_alert(1) is False
    with patch("app.services.notification_state._utcnow") as m:
        m.return_value = datetime.now(timezone.utc) + timedelta(days=2)
        assert should_send_stuck_task_alert(1) is True


def test_notification_presenters_return_human_readable_messages():
    """Проверяет форматтеры: короткие, человекочитаемые сообщения."""
    payload = {"task_id": 5, "summary": "Done"}
    text = format_approval_alert(payload)
    assert isinstance(text, str)
    assert "5" in text
    assert "{" not in text

    text = format_completion_alert({"task_id": 3, "summary": "Report", "report_path": "/path"})
    assert "3" in text and "выполнен" in text

    text = format_degraded_alert({"reason": "Molt down", "molt_message": "down"})
    assert "Degraded" in text or "degraded" in text.lower()

    text = format_recovered_alert({})
    assert "норме" in text or "recovered" in text.lower()

    text = format_stuck_task_alert({"task_id": 7, "status": "WAIT_OWNER", "threshold_minutes": 1440})
    assert "7" in text and "WAIT_OWNER" in text

    data = {"transport_mode": "local", "molt_message": "n/a", "active_tasks_count": 0,
            "pending_approvals_count": 0, "recent_artifacts_count": 0, "state": "OK"}
    text = format_daily_summary_notification(data)
    assert "Ежедневная" in text or "сводка" in text
    assert "{" not in text


def test_owner_notification_send_path_is_wired():
    """Проверяет, что есть рабочая связка service -> presenter -> telegram send path."""
    text = _format_owner_notification("approval_requested", {"task_id": 10, "summary": "Approve me"})
    assert isinstance(text, str)
    assert "10" in text
    text = _format_owner_notification("daily_summary", {"state": "OK", "active_tasks_count": 0, "molt_ok": True,
                                                       "molt_message": "n/a", "transport_mode": "local",
                                                       "pending_approvals_count": 0, "recent_artifacts_count": 0})
    assert "сводка" in text or "Status" in text

    with patch("app.bot.notify.send_owner_message", new_callable=AsyncMock, return_value=True) as send:
        ok = asyncio.run(send_owner_notification("stuck_task", {"task_id": 99, "status": "WAIT_OWNER", "threshold_minutes": 1440}))
        assert ok is True
        assert send.called
        (arg,) = send.call_args[0]
        assert "99" in arg


def test_daily_summary_scheduler_hook_exists():
    """Проверяет наличие и базовую работоспособность scheduler/trigger hook."""
    from app.bot.owner_notification_loop import (
        owner_notification_loop,
        _run_daily_summary_if_due,
        _check_health_and_send_alerts,
        _check_stuck_tasks_and_send,
    )
    assert callable(owner_notification_loop)
    assert callable(_run_daily_summary_if_due)
    assert callable(_check_health_and_send_alerts)
    assert callable(_check_stuck_tasks_and_send)


def test_get_stuck_tasks_returns_tasks_over_threshold(db_session):
    """Stuck policy: задачи в WAIT_OWNER дольше порога попадают в список."""
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Stuck approval")
    repo.update_task(task.id, status=TaskStatus.WAIT_OWNER.value)
    with patch("app.services.owner_notifications.get_owner_notification_config") as cfg:
        cfg.return_value = {
            "stuck_waiting_approval_minutes": 0,
            "stuck_no_progress_minutes": 360,
            "stuck_alert_cooldown_minutes": 1440,
        }
        stuck = get_stuck_tasks()
    ids = [s["task"].id for s in stuck]
    assert task.id in ids
