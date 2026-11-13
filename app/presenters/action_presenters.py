# app/presenters/action_presenters.py — Phase 9.8: human-readable action list and results
from __future__ import annotations

from typing import Any


def format_action_list(actions: list[dict[str, Any]], role: str) -> str:
    """Форматировать список доступных действий для Telegram/CLI."""
    if not actions:
        return "No actions available for your role."
    lines = ["Available actions (%s):" % role]
    for a in actions:
        name = a.get("action_name", "?")
        cat = a.get("category", "?")
        lines.append("  • %s (%s)" % (name, cat))
    return "\n".join(lines)


def format_action_result(result: dict[str, Any]) -> str:
    """Форматировать успешный или неуспешный результат действия."""
    success = result.get("success", False)
    summary = result.get("result_summary", "")
    if success:
        return "✅ %s" % summary
    err = result.get("error_message", "")
    if err:
        return "❌ %s\n%s" % (summary, err)
    return "❌ %s" % summary


def format_action_error(action_name: str, reason: str) -> str:
    """Форматировать ошибку (disallowed, not found)."""
    return "❌ Action '%s': %s" % (action_name, reason)


def format_action_confirmation_if_needed(action_name: str, result: dict[str, Any]) -> str | None:
    """Если действие требует подтверждения — вернуть текст; иначе None (baseline: все safe, подтверждение не требуется)."""
    if result.get("approval_required"):
        return "Action '%s' may require approval. Proceed?" % action_name
    return None
