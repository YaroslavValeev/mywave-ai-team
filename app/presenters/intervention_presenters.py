# app/presenters/intervention_presenters.py — Phase 11.7: intervention plan and bundle formatting
from __future__ import annotations

from typing import Any, List


def present_intervention_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Web/API view-model для intervention plan."""
    if not plan:
        return {}
    do_now = plan.get("do_now")
    do_next = plan.get("do_next")
    defer = plan.get("defer", [])
    return {
        "plan_id": plan.get("plan_id", ""),
        "scope_type": plan.get("scope_type", ""),
        "scope_key": plan.get("scope_key", ""),
        "plan_headline": plan.get("plan_headline", ""),
        "plan_reason": plan.get("plan_reason", ""),
        "priority_label": plan.get("priority_label", "medium"),
        "interventions": plan.get("interventions", [])[:10],
        "preferred_intervention": plan.get("preferred_intervention"),
        "fallback_intervention": plan.get("fallback_intervention"),
        "expected_effect": plan.get("expected_effect"),
        "risk_if_ignored": plan.get("risk_if_ignored"),
        "evidence_refs": plan.get("evidence_refs", []),
        "generated_at": plan.get("generated_at"),
        "do_now": do_now,
        "do_next": do_next,
        "defer": defer,
        "defer_count": len(defer),
    }


def present_intervention_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Web/API view-model для decision bundle."""
    if not bundle:
        return {}
    return {
        "decision_bundle_id": bundle.get("decision_bundle_id", ""),
        "bundle_type": bundle.get("bundle_type", ""),
        "subject_type": bundle.get("subject_type", ""),
        "subject_key": bundle.get("subject_key", ""),
        "headline": bundle.get("headline", ""),
        "why_now": bundle.get("why_now", ""),
        "top_problem": bundle.get("top_problem", "")[:200],
        "candidate_interventions": bundle.get("candidate_interventions", [])[:10],
        "preferred_sequence": bundle.get("preferred_sequence", []),
        "do_now": bundle.get("do_now"),
        "do_next": bundle.get("do_next"),
        "defer": bundle.get("defer", []),
        "evidence_summary": bundle.get("evidence_summary", []),
        "related_objects": bundle.get("related_objects", []),
        "plan": present_intervention_plan(bundle.get("plan", {})),
    }


def present_priority_interventions(raw: dict[str, Any]) -> dict[str, Any]:
    """Top interventions для portfolio view."""
    items = raw.get("items", [])[:10]
    cards = []
    for i, iv in enumerate(items):
        cards.append({
            "rank": i + 1,
            "intervention_id": iv.get("intervention_id", ""),
            "intervention_type": iv.get("intervention_type", ""),
            "target_layer": iv.get("target_layer", ""),
            "target_role": iv.get("target_role", ""),
            "reason": iv.get("reason", ""),
            "urgency": iv.get("urgency", "medium"),
            "safe_action_available": iv.get("safe_action_available", False),
            "safe_action_key": iv.get("safe_action_key"),
            "manual_path_required": iv.get("manual_path_required", True),
            "source_plan": iv.get("source_plan", ""),
        })
    return {"items": cards, "count": len(cards), "window_days": raw.get("window_days", 30)}


def present_preferred_sequence(bundle: dict[str, Any]) -> dict[str, Any]:
    """Компактный preferred sequence: do_now, do_next, defer_summary."""
    do_now = bundle.get("do_now")
    do_next = bundle.get("do_next")
    defer = bundle.get("defer", [])
    steps = []
    if do_now:
        steps.append({"step": 1, "label": "do_now", "intervention": do_now})
    if do_next:
        steps.append({"step": 2, "label": "do_next", "intervention": do_next})
    for j, d in enumerate(defer[:3]):
        steps.append({"step": 3 + j, "label": "defer", "intervention": d})
    return {
        "steps": steps,
        "do_now": do_now,
        "do_next": do_next,
        "defer_count": len(defer),
        "headline": bundle.get("headline", ""),
    }


def format_intervention_plan_telegram(plan: dict[str, Any], max_items: int = 3) -> str:
    """Telegram-friendly текст intervention plan."""
    do_now = plan.get("do_now")
    do_next = plan.get("do_next")
    defer = plan.get("defer", [])

    lines = [f"📋 {plan.get('plan_headline', 'Intervention plan')[:60]}"]
    lines.append(f"   {plan.get('plan_reason', '')[:80]}")

    if do_now:
        lines.append("")
        lines.append("1️⃣ Сейчас:")
        lines.append(f"   {do_now.get('reason', '')[:70]}")
        if do_now.get("safe_action_key"):
            lines.append(f"   /do {do_now['safe_action_key']}")
    if do_next:
        lines.append("")
        lines.append("2️⃣ Далее:")
        lines.append(f"   {do_next.get('reason', '')[:70]}")
        if do_next.get("safe_action_key"):
            lines.append(f"   /do {do_next['safe_action_key']}")
    if defer:
        lines.append("")
        lines.append(f"3️⃣ Отложить ({len(defer)}):")
        for d in defer[:max_items]:
            lines.append(f"   • {d.get('reason', '')[:55]}")
    return "\n".join(lines)


def format_intervention_bundle_telegram(bundle: dict[str, Any]) -> str:
    """Telegram-friendly текст decision bundle."""
    plan = bundle.get("plan", {})
    return format_intervention_plan_telegram(plan)


def format_priority_interventions_telegram(raw: dict[str, Any]) -> str:
    """Telegram: top interventions. Phase 12.3: defer hint."""
    items = raw.get("items", [])[:5]
    if not items:
        return "Нет приоритетных вмешательств за период."
    lines = ["🔝 Приоритетные вмешательства:"]
    for i, iv in enumerate(items, 1):
        lines.append(f"{i}. [{iv.get('urgency', '')}] {iv.get('reason', '')[:55]}")
        if iv.get("safe_action_key"):
            lines.append(f"   /do {iv['safe_action_key']}")
        if iv.get("intervention_id"):
            lines.append(f"   /defer_intervention {iv['intervention_id']}")
    return "\n".join(lines)


def format_preferred_sequence_telegram(seq: dict[str, Any]) -> str:
    """Telegram: preferred sequence."""
    steps = seq.get("steps", [])
    if not steps:
        return "Нет рекомендуемой последовательности."
    lines = ["📌 Рекомендуемый порядок:"]
    for s in steps[:4]:
        lab = s.get("label", "")
        iv = s.get("intervention", {})
        r = iv.get("reason", "")[:50]
        lines.append(f"  {lab}: {r}")
        if iv.get("safe_action_key"):
            lines.append(f"    /do {iv['safe_action_key']}")
    return "\n".join(lines)


def present_intervention_compact_card(iv: dict[str, Any]) -> dict[str, Any]:
    """Compact card для web (project/portfolio surfaces)."""
    if not iv:
        return {}
    return {
        "intervention_id": iv.get("intervention_id", ""),
        "intervention_type": iv.get("intervention_type", ""),
        "target_layer": iv.get("target_layer", ""),
        "target_role": iv.get("target_role", ""),
        "reason": (iv.get("reason", "") or iv.get("headline", ""))[:120],
        "urgency": iv.get("urgency", "medium"),
        "safe_action_available": iv.get("safe_action_available", False),
        "safe_action_key": iv.get("safe_action_key"),
        "manual_path_required": iv.get("manual_path_required", True),
        "expected_effect": iv.get("expected_effect"),
    }
