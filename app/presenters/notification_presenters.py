# app/presenters/notification_presenters.py — Phase 9.1: format owner notification messages for Telegram
from __future__ import annotations

from typing import Any

from app.presenters.owner_presenters import format_summary, format_approvals_list, format_artifacts_list
from app.presenters.owner_insight_presenters import format_weekly_digest
from app.presenters.owner_recommendation_presenters import (
    format_strategic_weekly_digest,
    format_monthly_digest_baseline,
)
from app.presenters.owner_portfolio_presenters import format_portfolio_weekly_digest


def format_daily_summary_notification(payload: dict[str, Any]) -> str:
    """Ежедневная сводка: коротко, по делу."""
    parts = [
        "📊 Ежедневная сводка",
        format_summary(payload),
    ]
    if payload.get("pending_approvals_list"):
        parts.append(format_approvals_list(payload["pending_approvals_list"]))
    if payload.get("recent_artifacts_list"):
        parts.append(format_artifacts_list(payload["recent_artifacts_list"]))
    return "\n\n".join(parts)


def format_approval_alert(payload: dict[str, Any]) -> str:
    """Уведомление: нужен approve по задаче."""
    task_id = payload.get("task_id", "?")
    summary = (payload.get("summary") or "")[:200]
    if summary:
        return f"⏳ Task #{task_id} ждёт решения\n\n{summary}"
    return f"⏳ Task #{task_id} ждёт решения (approve/rework/clarify)."


def format_completion_alert(payload: dict[str, Any]) -> str:
    """Задача выполнена."""
    task_id = payload.get("task_id", "?")
    summary = (payload.get("summary") or "")[:150]
    report = payload.get("report_path") or ""
    msg = f"✅ Task #{task_id} выполнен."
    if summary:
        msg += f"\n\n{summary}"
    if report:
        msg += f"\n\nОтчёт: {report}"
    return msg


def format_degraded_alert(payload: dict[str, Any]) -> str:
    """Система в режиме degraded."""
    reason = payload.get("reason") or "Molt/runtime недоступен"
    detail = payload.get("molt_message") or ""
    if detail:
        return f"⚠️ Degraded: {reason} ({detail}). Проверьте сервис."
    return f"⚠️ Degraded: {reason}. Проверьте сервис."


def format_recovered_alert(payload: dict[str, Any]) -> str:
    """Система восстановилась."""
    return "✅ Система снова в норме (recovered)."


def format_stuck_task_alert(payload: dict[str, Any]) -> str:
    """Задача зависла (ожидание / без прогресса)."""
    task_id = payload.get("task_id", "?")
    status = payload.get("status", "?")
    th = payload.get("threshold_minutes")
    th_str = f" (>{th} мин)" if th else ""
    return f"🔶 Task #{task_id} долго в статусе {status}{th_str}. Требуется внимание."


def format_weekly_digest_notification(payload: dict[str, Any]) -> str:
    """Еженедельная управленческая сводка."""
    return "🧭 Weekly management digest\n\n" + format_weekly_digest(payload)


def format_strategic_weekly_digest_notification(payload: dict[str, Any]) -> str:
    """Стратегическая недельная сводка (Phase 9.3)."""
    return "🧭 Strategic weekly digest\n\n" + format_strategic_weekly_digest(payload)


def format_monthly_digest_notification(payload: dict[str, Any]) -> str:
    """Месячная сводка (last 30 days)."""
    return "📅 Monthly digest\n\n" + format_monthly_digest_baseline(payload)


def format_portfolio_weekly_digest_notification(payload: dict[str, Any]) -> str:
    """Portfolio weekly digest (Phase 9.6): cross-project view."""
    return "📊 Portfolio weekly digest\n\n" + format_portfolio_weekly_digest(payload)
