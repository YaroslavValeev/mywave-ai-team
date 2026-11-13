# app/services/tuning_outcomes.py — Phase 11.3: verified tuning outcomes (explainable)
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from app.services.agent_tuning_store import get_candidate
from app.services.refinement_proposal_store import get_proposal
from app.services.tuning_outcome_store import (
    get_outcome_by_candidate,
    list_outcome_records,
    merge_outcome,
    outcome_id_for_candidate,
    get_outcome_record,
)


def _count_fallback_domain_step(domain_key: str, workflow_step: str, window_days: int) -> int:
    """Explainable: число audit specialization_fallback_used за окно для пары domain/step."""
    from app.storage.repositories import get_session_factory
    from app.storage.models import AuditEvent

    Session = get_session_factory()
    since_ts = datetime.now(timezone.utc) - timedelta(days=window_days)
    with Session() as session:
        evs = (
            session.query(AuditEvent)
            .filter(
                AuditEvent.event_type == "specialization_fallback_used",
                AuditEvent.created_at >= since_ts,
            )
            .all()
        )
    n = 0
    dk = (domain_key or "general").strip() or "general"
    wk = (workflow_step or "pipeline").strip() or "pipeline"
    for e in evs:
        p = e.payload_json or {}
        d = (p.get("effective_domain") or "general").strip() or "general"
        w = (p.get("workflow_step") or "pipeline").strip() or "pipeline"
        if d == dk and w == wk:
            n += 1
    return n


def record_tuning_baseline_on_patch_apply(
    proposal_id: str,
    *,
    patch_id: Optional[str] = None,
    window_days: int = 30,
) -> Optional[dict[str, Any]]:
    """
    Вызывается после успешного apply_patch_candidate для proposals с source_tuning_candidate_id.
    Фиксирует baseline fallback metrics (explainable).
    """
    p = get_proposal(proposal_id)
    if not p:
        return None
    cid = p.get("source_tuning_candidate_id")
    if not cid:
        return None
    c = get_candidate(cid)
    if not c:
        return None
    dk = c.get("domain_key") or "general"
    wk = c.get("workflow_step") or "pipeline"
    count = _count_fallback_domain_step(dk, wk, window_days)
    level = f"fallback_count={count} для domain={dk}, step={wk} (окно {window_days}д, baseline после apply)"
    now = datetime.now(timezone.utc).isoformat()
    oid = outcome_id_for_candidate(cid)
    existing = get_outcome_record(oid)
    created_at = existing.get("created_at") if existing else now
    return merge_outcome(oid, {
        "outcome_id": oid,
        "tuning_candidate_id": cid,
        "proposal_id": proposal_id,
        "patch_id": patch_id,
        "verification_window_days": window_days,
        "baseline_signal_level": level,
        "baseline_fallback_count": count,
        "post_apply_signal_level": None,
        "post_apply_fallback_count": None,
        "outcome_status": "pending_measurement",
        "outcome_reason": "Baseline зафиксирован при apply; сравните позже через evaluate",
        "improvement_detected": False,
        "followup_needed": True,
        "measured_at": now,
        "created_at": created_at,
    })


def evaluate_tuning_outcome(
    tuning_candidate_id: str,
    window_days: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """
    Сравнить baseline vs текущий fallback_count (rule-based, explainable).
    """
    c = get_candidate(tuning_candidate_id)
    if not c:
        return None
    oid = outcome_id_for_candidate(tuning_candidate_id)
    prop_id = c.get("proposal_id")
    p = get_proposal(prop_id) if prop_id else None
    wd = int(window_days or 30)
    now = datetime.now(timezone.utc).isoformat()
    dk = c.get("domain_key") or "general"
    wk = c.get("workflow_step") or "pipeline"

    if not p:
        return merge_outcome(oid, {
            "outcome_id": oid,
            "tuning_candidate_id": tuning_candidate_id,
            "proposal_id": None,
            "verification_window_days": wd,
            "outcome_status": "not_patch_applied",
            "outcome_reason": "Нет proposal или candidate не сконвертирован",
            "improvement_detected": False,
            "followup_needed": True,
            "post_apply_signal_level": None,
            "post_apply_fallback_count": None,
            "measured_at": now,
        })

    if (p.get("status") or "") != "applied":
        return merge_outcome(oid, {
            "outcome_id": oid,
            "tuning_candidate_id": tuning_candidate_id,
            "proposal_id": prop_id,
            "verification_window_days": wd,
            "outcome_status": "not_patch_applied",
            "outcome_reason": f"Proposal status={p.get('status')}, ожидается applied",
            "improvement_detected": False,
            "followup_needed": True,
            "measured_at": now,
        })

    post = _count_fallback_domain_step(dk, wk, wd)
    post_level = f"fallback_count={post} для domain={dk}, step={wk} (окно {wd}д, текущее)"

    existing = get_outcome_record(oid)
    baseline = existing.get("baseline_fallback_count") if existing else None

    if baseline is None:
        return merge_outcome(oid, {
            "outcome_id": oid,
            "tuning_candidate_id": tuning_candidate_id,
            "proposal_id": prop_id,
            "patch_id": existing.get("patch_id") if existing else None,
            "verification_window_days": wd,
            "post_apply_signal_level": post_level,
            "post_apply_fallback_count": post,
            "outcome_status": "insufficient_data",
            "outcome_reason": "Baseline отсутствует (apply до Phase 11.3 или без tuning source); нельзя сравнить",
            "improvement_detected": False,
            "followup_needed": True,
            "measured_at": now,
        })

    if post < baseline:
        status, reason, imp, follow = "improved", f"fallback_count снизился {baseline}→{post}", True, False
    elif post > baseline:
        status, reason, imp, follow = "worse", f"fallback_count вырос {baseline}→{post}", False, True
    else:
        status, reason, imp, follow = "unchanged", f"fallback_count без изменений ({post})", False, True

    if baseline == 0 and post == 0 and wd < 7:
        status, reason = "insufficient_data", "Мало данных в коротком окне для вывода"
        follow = True

    return merge_outcome(oid, {
        "outcome_id": oid,
        "tuning_candidate_id": tuning_candidate_id,
        "proposal_id": prop_id,
        "patch_id": existing.get("patch_id") if existing else None,
        "verification_window_days": wd,
        "baseline_signal_level": existing.get("baseline_signal_level"),
        "post_apply_signal_level": post_level,
        "post_apply_fallback_count": post,
        "outcome_status": status,
        "outcome_reason": reason,
        "improvement_detected": imp,
        "followup_needed": follow,
        "measured_at": now,
    })


def get_tuning_outcome(tuning_candidate_id: str) -> Optional[dict[str, Any]]:
    return get_outcome_by_candidate(tuning_candidate_id)


def list_tuning_outcomes(window_days: int = 30, limit: int = 50) -> dict[str, Any]:
    items = list_outcome_records(limit=limit)
    return {"items": items, "count": len(items), "window_days": window_days}


def get_tuning_outcome_summary(window_days: int = 30) -> dict[str, Any]:
    items = list_outcome_records(limit=200)
    improved = sum(1 for i in items if i.get("outcome_status") == "improved")
    worse = sum(1 for i in items if i.get("outcome_status") == "worse")
    unchanged = sum(1 for i in items if i.get("outcome_status") == "unchanged")
    pending = sum(1 for i in items if i.get("outcome_status") == "pending_measurement")
    insufficient = sum(1 for i in items if i.get("outcome_status") == "insufficient_data")
    not_applied = sum(1 for i in items if i.get("outcome_status") == "not_patch_applied")
    return {
        "window_days": window_days,
        "improved_count": improved,
        "worse_count": worse,
        "unchanged_count": unchanged,
        "pending_measurement_count": pending,
        "insufficient_data_count": insufficient,
        "not_patch_applied_count": not_applied,
        "total_outcomes": len(items),
        "explainable": True,
    }
