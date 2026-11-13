# app/presenters/production_readiness_presenters.py — Phase 12.2: readiness presentation

from __future__ import annotations

from typing import Any, Optional


def present_readiness_card(summary: dict[str, Any]) -> dict[str, Any]:
    """Compact readiness card для web/API."""
    return {
        "ready": summary.get("ready", False),
        "level": summary.get("level", "unknown"),
        "failed_checks": summary.get("failed_checks", []),
        "attention_items": summary.get("attention_items", []),
        "counts": summary.get("counts", {}),
    }


def present_failed_checks_summary(failed_checks: list[dict[str, Any]]) -> str:
    """Краткий текст failed checks для owner."""
    if not failed_checks:
        return "Все проверки пройдены."
    lines = [f"• {c.get('check_name', '?')}: {c.get('reason', '')[:80]}" for c in failed_checks[:5]]
    if len(failed_checks) > 5:
        lines.append(f"  ... и ещё {len(failed_checks) - 5}")
    return "\n".join(lines)


def format_readiness_telegram(summary: dict[str, Any]) -> str:
    """Telegram-friendly: краткий readiness summary."""
    ready = summary.get("ready", False)
    level = summary.get("level", "unknown")
    attention = summary.get("attention_items", [])

    if ready:
        return "✅ Система готова к эксплуатации."
    status = "⚠️ Degraded" if level == "degraded" else "❌ Not ready"
    lines = [f"{status}"]
    for a in attention[:3]:
        lines.append(f"• {a}")
    return "\n".join(lines)


def format_readiness_owner_text(summary: dict[str, Any]) -> str:
    """Owner-friendly текст: что сломано / что ок / что проверить."""
    ready = summary.get("ready", False)
    level = summary.get("level", "unknown")
    failed = summary.get("failed_checks", [])
    attention = summary.get("attention_items", [])

    if ready:
        return "Система готова к эксплуатации. Критичные проверки пройдены."
    if level == "not_ready":
        head = "Система не готова. Требуется внимание."
    else:
        head = "Система в состоянии degraded. Рекомендуется проверить."
    lines = [head]
    if attention:
        lines.append("Что проверить:")
        for a in attention[:3]:
            lines.append(f"  — {a}")
    return "\n".join(lines)
