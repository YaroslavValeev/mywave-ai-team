# app/bot/owner_notification_loop.py — Phase 9.1: scheduled summaries and proactive alerts
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_owner_notification_config
from app.bot.notify import send_owner_message
from app.services.owner_queries import get_system_status_summary
from app.services.owner_notifications import (
    build_daily_summary_payload,
    build_strategic_weekly_digest_payload,
    build_monthly_digest_payload,
    build_degraded_alert,
    build_recovered_alert,
    build_stuck_task_alert,
    should_send_daily_summary_now,
    should_send_weekly_digest_now,
    should_send_monthly_digest_now,
    should_send_degraded_alert_now,
    should_send_recovered_alert_now,
    should_send_stuck_task_alert,
    get_stuck_tasks,
)
from app.services.notification_state import (
    record_degraded_sent,
    record_recovered_sent,
    record_daily_summary_sent,
    record_weekly_digest_sent,
    record_monthly_digest_sent,
    record_stuck_alert_sent,
)
from app.presenters.notification_presenters import (
    format_daily_summary_notification,
    format_strategic_weekly_digest_notification,
    format_monthly_digest_notification,
    format_degraded_alert,
    format_recovered_alert,
    format_stuck_task_alert,
)

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 60
_previous_system_state: str = "OK"


def _parse_time(s: str) -> tuple[int, int]:
    """Parse 'HH:MM' -> (hour, minute). Default 09:00."""
    s = (s or "09:00").strip()
    try:
        parts = s.split(":", 1)
        h = int(parts[0]) if parts else 9
        m = int(parts[1]) if len(parts) > 1 else 0
        return h, m
    except (ValueError, IndexError):
        return 9, 0


async def _run_daily_summary_if_due() -> None:
    cfg = get_owner_notification_config()
    if not cfg.get("daily_summary_enabled", True):
        return
    if not should_send_daily_summary_now():
        return
    try:
        payload = build_daily_summary_payload()
        text = format_daily_summary_notification(payload)
        ok = await send_owner_message(text)
        if ok:
            record_daily_summary_sent()
            logger.info("Owner notification: daily summary sent")
    except Exception as e:
        logger.exception("Daily summary send failed: %s", e)


async def _run_weekly_digest_if_due() -> None:
    cfg = get_owner_notification_config()
    if not cfg.get("weekly_digest_enabled", True):
        return
    if not should_send_weekly_digest_now():
        return
    try:
        payload = build_strategic_weekly_digest_payload()
        text = format_strategic_weekly_digest_notification(payload)
        ok = await send_owner_message(text)
        if ok:
            record_weekly_digest_sent()
            logger.info("Owner notification: weekly (strategic) digest sent")
    except Exception as e:
        logger.exception("Weekly digest send failed: %s", e)


async def _run_monthly_digest_if_due() -> None:
    cfg = get_owner_notification_config()
    if not cfg.get("monthly_digest_enabled", True):
        return
    if not should_send_monthly_digest_now():
        return
    try:
        payload = build_monthly_digest_payload()
        text = format_monthly_digest_notification(payload)
        ok = await send_owner_message(text)
        if ok:
            record_monthly_digest_sent()
            logger.info("Owner notification: monthly digest sent")
    except Exception as e:
        logger.exception("Monthly digest send failed: %s", e)


async def _check_health_and_send_alerts() -> None:
    global _previous_system_state
    try:
        summary = get_system_status_summary()
        state = summary.get("state", "OK")
        molt_ok = summary.get("molt_ok", True)
        molt_msg = summary.get("molt_message", "")

        if state == "DEGRADED" and not molt_ok:
            if _previous_system_state == "OK" and should_send_degraded_alert_now():
                payload = build_degraded_alert(reason="Molt/runtime unavailable", molt_message=molt_msg)
                text = format_degraded_alert(payload)
                ok = await send_owner_message(text)
                if ok:
                    record_degraded_sent()
                    _previous_system_state = "DEGRADED"
                    logger.info("Owner notification: degraded alert sent")
            else:
                _previous_system_state = "DEGRADED"
        elif state == "OK":
            if _previous_system_state == "DEGRADED" and should_send_recovered_alert_now():
                payload = build_recovered_alert()
                text = format_recovered_alert(payload)
                ok = await send_owner_message(text)
                if ok:
                    record_recovered_sent()
                    _previous_system_state = "OK"
                    logger.info("Owner notification: recovered alert sent")
            else:
                _previous_system_state = "OK"
    except Exception as e:
        logger.exception("Health check for notifications failed: %s", e)


async def _check_stuck_tasks_and_send() -> None:
    cfg = get_owner_notification_config()
    if not cfg.get("stuck_task_alerts_enabled", True):
        return
    try:
        for item in get_stuck_tasks():
            task = item.get("task")
            if not task:
                continue
            task_id = getattr(task, "id", None)
            if task_id is None:
                continue
            if not should_send_stuck_task_alert(task_id):
                continue
            payload = build_stuck_task_alert(
                task_id=task_id,
                status=getattr(task, "status", "?"),
                threshold_minutes=item.get("threshold_minutes"),
            )
            text = format_stuck_task_alert(payload)
            ok = await send_owner_message(text)
            if ok:
                record_stuck_alert_sent(task_id)
                logger.info("Owner notification: stuck task alert sent for task %s", task_id)
    except Exception as e:
        logger.exception("Stuck task check failed: %s", e)


async def owner_notification_loop() -> None:
    """Background loop: daily summary at configured time, periodic health + stuck checks."""
    cfg = get_owner_notification_config()
    daily_h, daily_m = _parse_time(cfg.get("daily_summary_time", "09:00"))
    weekly_h, weekly_m = _parse_time(cfg.get("weekly_digest_time", "09:10"))
    weekly_day = int(cfg.get("weekly_digest_day", 1))
    monthly_h, monthly_m = _parse_time(cfg.get("monthly_digest_time", "09:15"))
    monthly_day = int(cfg.get("monthly_digest_day", 1))

    while True:
        try:
            now = datetime.now(timezone.utc)
            if now.hour == daily_h and now.minute == daily_m:
                await _run_daily_summary_if_due()
            if now.isoweekday() == weekly_day and now.hour == weekly_h and now.minute == weekly_m:
                await _run_weekly_digest_if_due()
            if now.day == monthly_day and now.hour == monthly_h and now.minute == monthly_m:
                await _run_monthly_digest_if_due()

            await _check_health_and_send_alerts()
            await _check_stuck_tasks_and_send()
        except asyncio.CancelledError:
            logger.info("Owner notification loop cancelled")
            break
        except Exception as e:
            logger.exception("Owner notification loop error: %s", e)

        await asyncio.sleep(CHECK_INTERVAL_SEC)
