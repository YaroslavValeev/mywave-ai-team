# app/presenters/role_domain_presenters.py — Phase 10.3: role-domain view-models and text
from __future__ import annotations

from typing import Any


def present_role_domain_recommendations(rec: dict[str, Any]) -> dict[str, Any]:
    """Компактная view-model для web/API."""
    return {
        "role_key": rec.get("role_key", ""),
        "recommended_domains": rec.get("recommended_domains", []),
        "current_domain_pressure": rec.get("current_domain_pressure", []),
        "why_this_role_needs_it": rec.get("why_this_role_needs_it", ""),
        "recommended_action": rec.get("recommended_action", ""),
        "evidence_summary": rec.get("evidence_summary", ""),
    }


def format_role_domain_telegram(rec: dict[str, Any]) -> str:
    """Краткий текст для Telegram: рекомендации по доменам для роли."""
    role = rec.get("role_key", "role")
    lines = [f"Роль: {role}", f"Домены для внимания: {', '.join(rec.get('recommended_domains', []) or ['—'])}"]
    if rec.get("evidence_summary"):
        lines.append(f"Основание: {rec['evidence_summary'][:200]}")
    if rec.get("recommended_action"):
        lines.append(f"Действие: {rec['recommended_action'][:150]}")
    return "\n".join(lines)


def format_domain_pressure_telegram(recs: list[dict[str, Any]]) -> str:
    """Сводка domain pressure по ролям для /domain_pressure."""
    if not recs:
        return "Нет данных по доменам по ролям."
    lines = ["Давление по доменам по ролям:"]
    for r in recs:
        role = r.get("role_key", "")
        domains = r.get("recommended_domains", [])[:3]
        evidence = (r.get("evidence_summary") or "")[:80]
        lines.append(f"  {role}: {', '.join(domains) or '—'} — {evidence}")
    return "\n".join(lines)
