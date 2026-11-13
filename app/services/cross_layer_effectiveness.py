# app/services/cross_layer_effectiveness.py — Phase 11.6: synthesis tuning + collaboration outcomes
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_effectiveness_slices(window_days: int = 30) -> List[dict[str, Any]]:
    """Срезы по каждому слою (tuning, collaboration) — read-only из stores."""
    slices: List[dict[str, Any]] = []

    try:
        from app.services.tuning_outcomes import get_tuning_outcome_summary, list_tuning_outcomes

        tun = get_tuning_outcome_summary(window_days=window_days)
        items = list_tuning_outcomes(window_days=window_days, limit=200).get("items", [])
        followup_t = (
            (tun.get("pending_measurement_count") or 0)
            + (tun.get("unchanged_count") or 0)
            + (tun.get("insufficient_data_count") or 0)
        )
        slices.append({
            "layer": "tuning",
            "window_days": window_days,
            "effective_count": tun.get("improved_count", 0),
            "ineffective_count": tun.get("worse_count", 0),
            "followup_count": followup_t,
            "total_in_window": tun.get("total_outcomes", len(items)),
            "evidence_source": "tuning_outcomes store",
            "evidence_refs": [{"id_type": "tuning_candidate_id", "sample_ids": [i.get("tuning_candidate_id") for i in items[:5] if i.get("tuning_candidate_id")]}] if items else [],
        })
    except Exception:
        pass

    try:
        from app.services.collaboration_outcomes import (
            get_collaboration_effectiveness_summary,
            list_collaboration_outcomes,
        )

        collab = get_collaboration_effectiveness_summary(window_days=window_days)
        items = list_collaboration_outcomes(window_days=window_days, limit=200).get("items", [])
        slices.append({
            "layer": "collaboration",
            "window_days": window_days,
            "effective_count": collab.get("effective_executions_count", 0),
            "ineffective_count": collab.get("ineffective_executions_count", 0),
            "followup_count": collab.get("followup_needed_count", 0),
            "total_in_window": collab.get("total_outcomes_in_window", len(items)),
            "evidence_source": "collaboration_outcomes store",
            "evidence_refs": [{"id_type": "execution_id", "sample_ids": [i.get("execution_id") for i in items[:5] if i.get("execution_id")]}] if items else [],
        })
    except Exception:
        pass

    return slices


def get_layer_alignment_signals(window_days: int = 30) -> List[dict[str, Any]]:
    """Рассогласования между слоями — collaboration improved + tuning worse и т.п."""
    items: List[dict[str, Any]] = []

    try:
        from app.services.tuning_outcomes import get_tuning_outcome_summary, list_tuning_outcomes
        from app.services.collaboration_outcomes import get_collaboration_effectiveness_summary, list_collaboration_outcomes

        tun = get_tuning_outcome_summary(window_days=window_days)
        collab = get_collaboration_effectiveness_summary(window_days=window_days)

        tun_improved = tun.get("improved_count", 0)
        tun_worse = tun.get("worse_count", 0)
        tun_followup = (tun.get("pending_measurement_count") or 0) + (tun.get("unchanged_count") or 0) + (tun.get("insufficient_data_count") or 0)
        collab_eff = collab.get("effective_executions_count", 0)
        collab_ineff = collab.get("ineffective_executions_count", 0)
        collab_followup = collab.get("followup_needed_count", 0)

        if collab_eff >= 1 and tun_worse >= 1:
            worse_items = [i for i in list_tuning_outcomes(limit=50).get("items", []) if i.get("outcome_status") == "worse"]
            refs = [{"id_type": "tuning_candidate_id", "id_value": i.get("tuning_candidate_id")} for i in worse_items[:3] if i.get("tuning_candidate_id")]
            items.append({
                "headline": "Collaboration улучшил, tuning — ухудшил",
                "reason": f"collaboration effective={collab_eff}, tuning worse={tun_worse}",
                "conflict_type": "collaboration_improved_tuning_worse",
                "evidence_refs": refs,
            })

        if collab_followup >= 2 and tun_followup >= 1:
            items.append({
                "headline": "Оба слоя требуют follow-up",
                "reason": f"collaboration followup={collab_followup}, tuning followup={tun_followup}",
                "conflict_type": "both_need_followup",
                "evidence_refs": [],
            })
    except Exception:
        pass

    return items


def synthesize_cross_layer_summary(window_days: int = 30) -> dict[str, Any]:
    """Единая сводка: slices + alignment items."""
    slices = build_effectiveness_slices(window_days=window_days)
    alignment = get_layer_alignment_signals(window_days=window_days)
    return {
        "window_days": window_days,
        "slices": slices,
        "alignment_items": alignment,
        "explainable": True,
        "synthesized_at": _now(),
    }


def list_projects_effectiveness_cross_cut(project_key: str, window_days: int = 30) -> dict[str, Any]:
    """Проектный срез (collaboration outcomes по project). Tuning пока без project-scoped slice."""
    try:
        from app.services.collaboration_outcomes import list_collaboration_outcomes

        raw = list_collaboration_outcomes(window_days=window_days, limit=300).get("items", [])
        proj_items = [i for i in raw if (i.get("subject_type") or "").lower() == "project" and str(i.get("subject_key")) == str(project_key)]
        return {
            "project_key": project_key,
            "window_days": window_days,
            "collaboration_outcomes_count": len(proj_items),
            "effective": sum(1 for i in proj_items if i.get("effectiveness_label") == "effective"),
            "ineffective": sum(1 for i in proj_items if i.get("effectiveness_label") == "ineffective"),
            "evidence_refs": [{"id_type": "execution_id", "id_value": i.get("execution_id")} for i in proj_items[:5] if i.get("execution_id")],
        }
    except Exception:
        return {"project_key": project_key, "window_days": window_days, "collaboration_outcomes_count": 0}
