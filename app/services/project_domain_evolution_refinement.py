# app/services/project_domain_evolution_refinement.py — Phase 11.9: evolution refinement layer
from __future__ import annotations

from typing import Any, List

from app.services.project_domain_lifecycle import (
    get_project_domain_lifecycle,
    list_project_domain_lifecycles,
    get_project_domain_drift_signals,
    get_project_domain_diversification_signals,
    get_project_domain_instability_signals,
    get_cross_project_domain_lifecycle_summary,
)
from app.services.project_domain_mapping import get_project_domain_profile

# Thresholds (from contracts)
DRIFT_HARMFUL_MIN_TASKS = 8
DRIFT_OVERRIDE_RATE_HARMFUL = 0.15
DRIFT_OVERRIDE_RATE_MONITOR = 0.10
DIVERSIFICATION_OVERRIDE_RATE = 0.20
DOMAINS_UNSTABLE_MIX_COUNT = 3
DOMAIN_MIN_SHARE_FOR_MIX = 0.10


def _compute_refinement_class(lc: dict[str, Any], profile: dict[str, Any]) -> tuple[str, str, str]:
    """
    Returns (refinement_class, owner_answer, intervention_preferred).
    refinement_class: weak_signal | transitional | normal_evolution | attention_needed
    owner_answer: normal_evolution | review_recommended | refinement_or_tuning | owner_attention
    intervention_preferred: refinement_review | tuning_review | owner_attention | —
    """
    state = lc.get("lifecycle_state", "")
    drift = bool(lc.get("domain_drift_signal"))
    diversif = bool(lc.get("domain_diversification_signal"))
    instab = bool(lc.get("domain_instability_signal"))
    task_prev = lc.get("task_count_previous") or 0
    task_curr = lc.get("task_count_current") or 0
    total_tasks = task_prev + task_curr
    override_count = profile.get("override_count") or 0
    task_count = profile.get("task_count") or 0
    override_rate = override_count / task_count if task_count else 0
    domain_mix = lc.get("domain_mix") or {}
    domains_with_share = [d for d, c in domain_mix.items() if (sum(domain_mix.values()) or 1) and (c / (sum(domain_mix.values()) or 1)) > DOMAIN_MIN_SHARE_FOR_MIX]

    # 1. weak_signal
    if state == "weak_signal":
        return "weak_signal", "normal_evolution", "—"

    # 2. override_heavy → owner_attention
    if state == "override_heavy":
        return "attention_needed", "owner_attention", "owner_attention"

    # 3. unstable → owner_attention
    if state == "unstable" or instab:
        return "attention_needed", "owner_attention", "owner_attention"

    # 4. drifting → transitional or attention_needed
    if drift:
        if total_tasks < DRIFT_HARMFUL_MIN_TASKS:
            return "transitional", "review_recommended", "refinement_review"
        if override_rate > DRIFT_OVERRIDE_RATE_HARMFUL or instab:
            return "attention_needed", "refinement_or_tuning", "refinement_review"
        if total_tasks >= 12 and override_rate > DRIFT_OVERRIDE_RATE_MONITOR:
            return "attention_needed", "refinement_or_tuning", "refinement_review"
        return "transitional", "review_recommended", "refinement_review"

    # 5. stable_multi_domain → normal_evolution or attention_needed (unstable mix)
    if state == "stable_multi_domain" or diversif:
        if len(domains_with_share) >= DOMAINS_UNSTABLE_MIX_COUNT:
            return "attention_needed", "refinement_or_tuning", "refinement_review"
        if override_rate > DIVERSIFICATION_OVERRIDE_RATE or instab:
            return "attention_needed", "refinement_or_tuning", "refinement_review"
        return "normal_evolution", "normal_evolution", "—"

    # 6. stable_single_domain
    return "normal_evolution", "normal_evolution", "—"


def _linked_to_refinement_backlog(project_key: str) -> bool:
    """Check if there are open refinement proposals for this project."""
    try:
        from app.services.refinement_proposals import list_refinement_proposals
        items = list_refinement_proposals(status="proposed", limit=50) + list_refinement_proposals(status="accepted", limit=50)
        return any(str(p.get("project_key") or p.get("target_key") or "").startswith(project_key) or project_key in str(p.get("target_key") or "") for p in items)
    except Exception:
        return False


def get_project_domain_evolution_refinement(project_key: str, window_days: int = 30) -> dict[str, Any]:
    """
    Evolution refinement для одного проекта: refinement_class, owner_answer, intervention_needed, evidence.
    Phase 11.9.
    """
    lc = get_project_domain_lifecycle(project_key, window_days=window_days)
    profile = get_project_domain_profile(project_key)
    refinement_class, owner_answer, intervention_preferred = _compute_refinement_class(lc, profile)
    linked = _linked_to_refinement_backlog(project_key)
    intervention_needed = refinement_class == "attention_needed"

    return {
        "project_key": project_key,
        "lifecycle_state": lc.get("lifecycle_state"),
        "refinement_class": refinement_class,
        "owner_answer": owner_answer,
        "intervention_needed": intervention_needed,
        "intervention_preferred": intervention_preferred if intervention_needed else None,
        "linked_to_refinement_backlog": linked,
        "evidence_summary": [
            lc.get("reason", ""),
            f"Доминанта: {lc.get('current_dominant_domain') or '—'}",
            f"Задачи: prev={lc.get('task_count_previous')}, curr={lc.get('task_count_current')}",
        ][:5],
        "window_days": window_days,
        "domain_drift_signal": lc.get("domain_drift_signal"),
        "domain_diversification_signal": lc.get("domain_diversification_signal"),
        "domain_instability_signal": lc.get("domain_instability_signal"),
    }


def list_project_domain_attention_items(window_days: int = 30, limit: int = 20) -> List[dict[str, Any]]:
    """Список проектов с attention_needed (вмешательство требуется). Phase 11.9."""
    lifecycles = list_project_domain_lifecycles(window_days=window_days, limit=100)
    out: List[dict[str, Any]] = []
    for lc in lifecycles:
        pk = lc.get("project_key")
        if not pk:
            continue
        ref = get_project_domain_evolution_refinement(pk, window_days=window_days)
        if ref.get("refinement_class") != "attention_needed":
            continue
        out.append({
            "project_key": pk,
            "attention_reason": ref.get("evidence_summary", [""])[0] or "Требуется внимание",
            "refinement_class": ref.get("refinement_class"),
            "owner_answer": ref.get("owner_answer"),
            "intervention_preferred": ref.get("intervention_preferred"),
            "linked_to_refinement_backlog": ref.get("linked_to_refinement_backlog"),
            "evidence_summary": ref.get("evidence_summary", []),
            "lifecycle_state": ref.get("lifecycle_state"),
        })
    return out[:limit]


def get_drift_requiring_intervention(window_days: int = 30, limit: int = 15) -> List[dict[str, Any]]:
    """Дрифтующие проекты, где refinement_class = attention_needed (harmful drift). Phase 11.9."""
    drift_signals = get_project_domain_drift_signals(window_days=window_days, limit=50)
    out: List[dict[str, Any]] = []
    for lc in drift_signals:
        pk = lc.get("project_key")
        if not pk:
            continue
        ref = get_project_domain_evolution_refinement(pk, window_days=window_days)
        if ref.get("refinement_class") == "attention_needed" and ref.get("domain_drift_signal"):
            out.append({**ref, "drift_type": "harmful"})
    return out[:limit]


def get_diversification_requiring_review(window_days: int = 30, limit: int = 15) -> List[dict[str, Any]]:
    """Diversification проекты, где refinement_class = attention_needed (unstable mix). Phase 11.9."""
    diversif_signals = get_project_domain_diversification_signals(window_days=window_days, limit=50)
    out: List[dict[str, Any]] = []
    for lc in diversif_signals:
        pk = lc.get("project_key")
        if not pk:
            continue
        ref = get_project_domain_evolution_refinement(pk, window_days=window_days)
        if ref.get("refinement_class") == "attention_needed" and ref.get("domain_diversification_signal"):
            out.append({**ref, "diversification_type": "unstable_mix"})
    return out[:limit]


def get_project_domain_transition_summary(window_days: int = 30) -> dict[str, Any]:
    """Сводка: attention items, drift requiring intervention, diversification requiring review. Phase 11.9."""
    attention = list_project_domain_attention_items(window_days=window_days, limit=20)
    drift = get_drift_requiring_intervention(window_days=window_days, limit=10)
    diversif = get_diversification_requiring_review(window_days=window_days, limit=10)
    summary_raw = get_cross_project_domain_lifecycle_summary(window_days=window_days)
    return {
        "window_days": window_days,
        "attention_items_count": len(attention),
        "drift_requiring_intervention_count": len(drift),
        "diversification_requiring_review_count": len(diversif),
        "attention_items": attention,
        "drift_requiring_intervention": drift,
        "diversification_requiring_review": diversif,
        "lifecycle_summary": summary_raw.get("summary", ""),
    }
