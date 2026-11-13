# app/services/domain_context_packs.py — Phase 9.9: context pack generation for domains (no raw know_proff in runtime)
from __future__ import annotations

from typing import Any

from app.services.domain_registry import get_domain, get_domain_context_pack
from app.services.expert_routing import suggest_domains_for_task


def build_context_pack(domain_key: str) -> dict[str, Any] | None:
    """Собрать контекст-пак по домену: summary, strengths, typical tasks, tools, methods, not for."""
    pack = get_domain_context_pack(domain_key)
    if not pack:
        return None
    dom = get_domain(domain_key)
    if not dom:
        return pack
    return {
        "domain_key": pack.get("domain_key"),
        "canonical_name": pack.get("canonical_name"),
        "summary": pack.get("summary"),
        "strengths": pack.get("routing_keywords", []),
        "typical_tasks": pack.get("typical_requests", []),
        "tools": [],
        "methods": [],
        "interaction_style": "См. source_file: %s" % (dom.get("source_file") or ""),
        "not_for": [],
    }


def build_task_context_pack(task_text: str) -> dict[str, Any]:
    """Контекст-пак для задачи: primary domain pack + опционально secondary."""
    suggestions = suggest_domains_for_task(task_text, limit=3)
    primary = next((s for s in suggestions if s.get("is_primary") or s.get("is_fallback")), None)
    if not primary:
        return {"primary": None, "secondary": [], "explain": "Нет подходящего домена."}
    pk = primary.get("domain_key")
    primary_pack = build_context_pack(pk) if pk else None
    secondary = [s for s in suggestions if s.get("is_secondary")][:2]
    secondary_packs = []
    for s in secondary:
        sk = s.get("domain_key")
        if sk:
            sp = build_context_pack(sk)
            if sp:
                secondary_packs.append(sp)
    return {
        "primary": primary_pack,
        "primary_domain_key": pk,
        "secondary": secondary_packs,
        "explain": primary.get("reason", ""),
        "matched_keywords": primary.get("matched_keywords", []),
    }


def build_multi_domain_context_pack(domain_keys: list[str]) -> dict[str, Any]:
    """Контекст-паки для нескольких доменов."""
    packs = []
    for dk in domain_keys:
        p = build_context_pack(dk)
        if p:
            packs.append(p)
    return {"domains": packs, "count": len(packs)}
