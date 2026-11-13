# app/services/domain_triage.py — Phase 10.0: domain-aware triage and context selection
from __future__ import annotations

from typing import Any

from app.services.expert_routing import suggest_domains_for_task
from app.services.domain_context_packs import build_context_pack

DOMAIN_ROUTING_VERSION = "1.0"
MAX_SECONDARY_PACKS = 2


def triage_domains_for_task(task_text: str) -> dict[str, Any]:
    """
    Определить primary/secondary expertise domains по тексту задачи.
    Возвращает: primary_domain_key, secondary_domain_keys, suggestions, reason, matched_keywords.
    """
    suggestions = suggest_domains_for_task((task_text or "").strip(), limit=5)
    primary = next((s for s in suggestions if s.get("is_primary") or s.get("is_fallback")), None)
    secondary = [s for s in suggestions if s.get("is_secondary")][:MAX_SECONDARY_PACKS]

    primary_key = primary.get("domain_key") if primary else None
    secondary_keys = [s.get("domain_key") for s in secondary if s.get("domain_key")]

    reason = (primary.get("reason") or "Нет совпадений") if primary else "Нет совпадений"
    matched = list(primary.get("matched_keywords") or [])[:10] if primary else []

    score = float(primary.get("score") or 0) if primary else 0.0
    if score >= 3:
        confidence = "high"
    elif score >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    source = "fallback" if (primary and primary.get("is_fallback")) else "triage"

    return {
        "primary_domain_key": primary_key,
        "secondary_domain_keys": secondary_keys,
        "suggestions": suggestions,
        "reason": reason,
        "matched_keywords": matched,
        "confidence": confidence,
        "source": source,
    }


def build_task_domain_metadata(task_text: str) -> dict[str, Any]:
    """
    Полный task-domain metadata для прикрепления к задаче или отображения.
    """
    triage_result = triage_domains_for_task(task_text)
    primary = triage_result.get("primary_domain_key")
    secondary = triage_result.get("secondary_domain_keys") or []
    context_pack_keys = [primary] if primary else []
    context_pack_keys.extend([k for k in secondary if k and k not in context_pack_keys][:MAX_SECONDARY_PACKS])

    return {
        "primary_domain": primary,
        "secondary_domains": secondary,
        "domain_confidence": triage_result.get("confidence", "low"),
        "domain_reason": triage_result.get("reason", ""),
        "matched_keywords": triage_result.get("matched_keywords", []),
        "context_pack_keys": context_pack_keys,
        "domain_routing_version": DOMAIN_ROUTING_VERSION,
        "domain_selection_source": triage_result.get("source", "triage"),
    }


def select_context_for_task(task_text: str) -> dict[str, Any]:
    """
    Выбор context packs по policy: primary + до MAX_SECONDARY_PACKS secondary.
    Возвращает: selected_context_packs (list of keys), compact_context (краткий текст), primary_domain_key, reason.
    """
    meta = build_task_domain_metadata(task_text)
    keys = meta.get("context_pack_keys") or []
    packs = []
    compact_parts = []

    for dk in keys[: 1 + MAX_SECONDARY_PACKS]:
        pack = build_context_pack(dk)
        if pack:
            packs.append(pack)
            summary = (pack.get("summary") or "")[:400]
            strengths = (pack.get("strengths") or [])[:5]
            compact_parts.append(f"[{pack.get('canonical_name', dk)}] {summary}")
            if strengths:
                compact_parts.append("Ключевые слова: " + ", ".join(strengths[:5]))

    compact_context = "\n".join(compact_parts)[:1500] if compact_parts else ""

    return {
        "selected_context_packs": keys,
        "compact_context": compact_context,
        "primary_domain_key": meta.get("primary_domain"),
        "reason": meta.get("domain_reason"),
        "packs": packs,
    }


def explain_task_domain_selection(task_text: str) -> str:
    """Человекочитаемое объяснение выбора домена для задачи."""
    meta = build_task_domain_metadata(task_text)
    primary = meta.get("primary_domain") or "—"
    reason = meta.get("domain_reason") or "—"
    kw = meta.get("matched_keywords", [])
    kw_str = ", ".join(kw[:6]) if kw else "—"
    return f"Домен: {primary}. Причина: {reason}. Совпадения: {kw_str}"
