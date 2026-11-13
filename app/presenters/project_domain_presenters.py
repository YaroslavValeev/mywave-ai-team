# app/presenters/project_domain_presenters.py — Phase 10.3: project-domain view-models and text
from __future__ import annotations

from typing import Any


def present_project_domain_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Компактная view-model для web/API."""
    return {
        "project_key": profile.get("project_key", ""),
        "dominant_domain": profile.get("dominant_domain"),
        "secondary_domains": profile.get("secondary_domains", []),
        "domain_distribution": profile.get("domain_distribution", {}),
        "mapping_confidence": profile.get("mapping_confidence", "low"),
        "mismatch_signals": profile.get("mismatch_signals", []),
        "task_count": profile.get("task_count", 0),
        "override_count": profile.get("override_count", 0),
    }


def present_project_domain_distribution(profile: dict[str, Any]) -> str:
    """Человекочитаемое распределение для Telegram/карточки."""
    dist = profile.get("domain_distribution", {})
    if not dist:
        return "Нет данных по доменам."
    parts = [f"{d}: {c}" for d, c in sorted(dist.items(), key=lambda x: -x[1])[:5]]
    return "Распределение: " + ", ".join(parts)


def present_project_domain_mismatch_signals(profile: dict[str, Any]) -> str:
    """Текст по mismatch для карточки."""
    signals = profile.get("mismatch_signals", [])
    if not signals:
        return ""
    return " | ".join([s.get("reason", s.get("type", "")) for s in signals])


def format_project_domain_telegram(profile: dict[str, Any]) -> str:
    """Краткий текст для Telegram: /project_domain <key>."""
    lines = [f"Проект: {profile.get('project_key', '—')}"]
    dom = profile.get("dominant_domain")
    if dom:
        lines.append(f"Доминирующий домен: {dom}")
        lines.append(present_project_domain_distribution(profile))
    else:
        lines.append("Доминирующий домен: не определён (мало активных задач)")
    mismatch = present_project_domain_mismatch_signals(profile)
    if mismatch:
        lines.append(f"Сигналы: {mismatch}")
    return "\n".join(lines)
