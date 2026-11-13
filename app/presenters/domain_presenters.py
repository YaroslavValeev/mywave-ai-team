# app/presenters/domain_presenters.py — Phase 9.9: owner/GM-friendly domain and routing presentation
from __future__ import annotations

from typing import Any


def present_domain_registry_list(domains: list[dict[str, Any]]) -> dict[str, Any]:
    """Структурированный список доменов для API/UI."""
    return {
        "total": len(domains),
        "domains": [
            {
                "domain_key": d.get("domain_key"),
                "canonical_name": d.get("canonical_name"),
                "source_file": d.get("source_file"),
                "structure_type": d.get("structure_type"),
                "summary": (d.get("summary") or "")[:200],
            }
            for d in domains
        ],
    }


def present_domain_card(domain: dict[str, Any] | None) -> dict[str, Any] | None:
    """Карточка домена для страницы /owner/domain/{key}."""
    if not domain:
        return None
    return {
        "domain_key": domain.get("domain_key"),
        "canonical_name": domain.get("canonical_name"),
        "source_file": domain.get("source_file"),
        "structure_type": domain.get("structure_type"),
        "summary": domain.get("summary"),
        "routing_keywords": domain.get("routing_keywords", []),
        "typical_requests": domain.get("typical_requests", []),
        "aliases": domain.get("aliases", []),
        "notes": domain.get("notes"),
    }


def present_expert_profile(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    """Экспертный профиль для отображения."""
    if not profile:
        return None
    return {
        "expert_profile_key": profile.get("expert_profile_key"),
        "domain_key": profile.get("domain_key"),
        "profile_name": profile.get("profile_name"),
        "scope": profile.get("scope"),
        "strengths": profile.get("strengths", []),
        "good_for": profile.get("good_for", []),
        "not_for": profile.get("not_for", []),
    }


def present_routing_result(suggestions: list[dict[str, Any]], task_preview: str = "") -> dict[str, Any]:
    """Explainable результат routing для задачи."""
    primary = next((s for s in suggestions if s.get("is_primary") or s.get("is_fallback")), None)
    secondary = [s for s in suggestions if s.get("is_secondary")]
    return {
        "task_preview": (task_preview or "")[:200],
        "primary": primary,
        "secondary": secondary,
        "all": suggestions,
        "explainable": True,
    }


def format_domain_list_text(domains: list[dict[str, Any]]) -> str:
    """Текст списка доменов для Telegram/CLI."""
    if not domains:
        return "Нет доменов в реестре."
    lines = ["Домены экспертизы (%d):" % len(domains)]
    for d in domains:
        key = d.get("domain_key", "?")
        name = d.get("canonical_name", "?")
        lines.append("  • %s — %s" % (key, name))
    return "\n".join(lines)


def format_domain_card_text(domain: dict[str, Any] | None) -> str:
    """Текст карточки домена для Telegram/CLI."""
    if not domain:
        return "Домен не найден."
    lines = [
        "📌 %s" % domain.get("canonical_name", "?"),
        "Ключ: %s" % domain.get("domain_key", "?"),
        "Файл: %s" % domain.get("source_file", "?"),
        "",
        (domain.get("summary") or "—")[:400],
    ]
    if domain.get("routing_keywords"):
        lines.append("\nКлючевые слова: " + ", ".join(domain.get("routing_keywords", [])[:8]))
    return "\n".join(lines)


def present_task_domain_hint(domain_metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Компактное представление domain hint для task card (Phase 10.0)."""
    if not domain_metadata or not domain_metadata.get("primary_domain"):
        return None
    return {
        "primary_domain": domain_metadata.get("primary_domain"),
        "secondary_domains": domain_metadata.get("secondary_domains", []),
        "reason": (domain_metadata.get("domain_reason") or "")[:120],
        "confidence": domain_metadata.get("domain_confidence", "low"),
    }


def format_routing_result_text(suggestions: list[dict[str, Any]], task_preview: str = "") -> str:
    """Текст результата routing с объяснением."""
    if not suggestions:
        return "По задаче не подобран ни один домен."
    lines = []
    if task_preview:
        lines.append("Задача: %s" % task_preview[:150])
    primary = next((s for s in suggestions if s.get("is_primary") or s.get("is_fallback")), None)
    if primary:
        lines.append("\nОсновной домен: %s" % primary.get("canonical_name", primary.get("domain_key")))
        lines.append("Причина: %s" % (primary.get("reason") or "—"))
        if primary.get("matched_keywords"):
            lines.append("Совпадения: " + ", ".join(primary.get("matched_keywords", [])[:6]))
    secondary = [s for s in suggestions if s.get("is_secondary")]
    if secondary:
        lines.append("\nДоп. домены: " + ", ".join((s.get("canonical_name") or s.get("domain_key") or "?") for s in secondary))
    return "\n".join(lines)
