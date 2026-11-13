# app/services/notification_state.py — Phase 9.1: anti-spam state for owner notifications
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory state (process-scoped). Optional: persist to file for restart resilience.
_last_degraded_alert_at: Optional[datetime] = None
_last_recovered_alert_at: Optional[datetime] = None
_last_daily_summary_at: Optional[datetime] = None
_last_weekly_digest_at: Optional[datetime] = None
_last_monthly_digest_at: Optional[datetime] = None
_degraded_observed: bool = False
_last_stuck_alert_by_task: dict[int, datetime] = {}

# Cooldowns (minutes)
DEGRADED_COOLDOWN_MINUTES = 60
RECOVERED_AFTER_DEGRADED = True  # recovered only after we sent degraded
STUCK_COOLDOWN_MINUTES = 1440  # 24h per task
DAILY_SUMMARY_COOLDOWN_MINUTES = 23 * 60  # ~1 day
WEEKLY_DIGEST_COOLDOWN_MINUTES = 6 * 24 * 60  # ~1 week
MONTHLY_DIGEST_COOLDOWN_MINUTES = 28 * 24 * 60  # ~1 month


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def record_degraded_sent() -> None:
    global _last_degraded_alert_at, _degraded_observed
    _last_degraded_alert_at = _utcnow()
    _degraded_observed = True


def record_recovered_sent() -> None:
    global _last_recovered_alert_at, _degraded_observed
    _last_recovered_alert_at = _utcnow()
    _degraded_observed = False


def record_daily_summary_sent() -> None:
    global _last_daily_summary_at
    _last_daily_summary_at = _utcnow()


def record_weekly_digest_sent() -> None:
    global _last_weekly_digest_at
    _last_weekly_digest_at = _utcnow()


def record_stuck_alert_sent(task_id: int) -> None:
    _last_stuck_alert_by_task[task_id] = _utcnow()


def should_send_degraded_alert(cooldown_minutes: int = DEGRADED_COOLDOWN_MINUTES) -> bool:
    """Send degraded at most once per degraded period (until recovered). After recovered, next degraded is allowed."""
    if _last_recovered_alert_at and _last_degraded_alert_at and _last_recovered_alert_at > _last_degraded_alert_at:
        return True  # new period: we already sent recovered, next degraded is allowed
    if _last_degraded_alert_at and (not _last_recovered_alert_at or _last_recovered_alert_at < _last_degraded_alert_at):
        return False  # already sent degraded in this period, wait for recovery
    return True


def should_send_recovered_alert() -> bool:
    """Send recovered only once after we had sent a degraded alert."""
    if not _degraded_observed:
        return False
    if _last_recovered_alert_at and _last_degraded_alert_at and _last_recovered_alert_at >= _last_degraded_alert_at:
        return False  # already sent recovered for this degraded period
    return True


def should_send_daily_summary(cooldown_minutes: int = DAILY_SUMMARY_COOLDOWN_MINUTES) -> bool:
    if _last_daily_summary_at is None:
        return True
    return (_utcnow() - _last_daily_summary_at).total_seconds() >= cooldown_minutes * 60


def should_send_stuck_task_alert(task_id: int, cooldown_minutes: int = STUCK_COOLDOWN_MINUTES) -> bool:
    last = _last_stuck_alert_by_task.get(task_id)
    if last is None:
        return True
    return (_utcnow() - last).total_seconds() >= cooldown_minutes * 60


def should_send_weekly_digest(cooldown_minutes: int = WEEKLY_DIGEST_COOLDOWN_MINUTES) -> bool:
    if _last_weekly_digest_at is None:
        return True
    return (_utcnow() - _last_weekly_digest_at).total_seconds() >= cooldown_minutes * 60


def record_monthly_digest_sent() -> None:
    global _last_monthly_digest_at
    _last_monthly_digest_at = _utcnow()


def should_send_monthly_digest(cooldown_minutes: int = MONTHLY_DIGEST_COOLDOWN_MINUTES) -> bool:
    if _last_monthly_digest_at is None:
        return True
    return (_utcnow() - _last_monthly_digest_at).total_seconds() >= cooldown_minutes * 60


def get_last_daily_summary_at() -> Optional[datetime]:
    return _last_daily_summary_at


def reset_for_tests() -> None:
    """Сброс состояния (только для тестов)."""
    global _last_degraded_alert_at, _last_recovered_alert_at, _last_daily_summary_at, _last_weekly_digest_at, _last_monthly_digest_at, _degraded_observed
    global _last_stuck_alert_by_task
    _last_degraded_alert_at = None
    _last_recovered_alert_at = None
    _last_daily_summary_at = None
    _last_weekly_digest_at = None
    _last_monthly_digest_at = None
    _degraded_observed = False
    _last_stuck_alert_by_task = {}
