# app/services/agent_tuning_workflows.py — Phase 11.2: agent-specific tuning and execution lane improvement
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from app.services.domain_specialization_analytics import (
    get_refinement_signals,
    get_refinement_backlog,
    get_specialization_fallback_summary,
    get_specialization_hotspots,
    get_override_hotspots,
)
from app.services.agent_tuning_store import (
    list_candidates,
    get_candidate,
    save_candidate,
    update_candidate_status,
)
from app.services.refinement_proposals import generate_refinement_proposals
from app.services.refinement_proposal_store import save_proposal, get_proposal


def _candidate_type_from_signal(signal_type: str, reason: str) -> str:
    if "fallback" in (signal_type or "").lower() or "fallback" in (reason or "").lower():
        return "expand_specialization_keywords"
    if "override" in (signal_type or "").lower():
        return "adjust_execution_focus"
    if "unstable" in (signal_type or "").lower():
        return "review_fallback_strategy"
    return "review_specialization_profile"


def _generate_candidate_id(signal_type: str, domain_key: str, workflow_step: str, project_key: str) -> str:
    key = f"{signal_type}:{domain_key or ''}:{workflow_step or ''}:{project_key or ''}".strip(":")
    return f"tc_{abs(hash(key)) % 1000000:06d}"


def generate_tuning_candidates(window_days: int = 30, limit: int = 15) -> List[dict[str, Any]]:
    """Создать tuning candidates из specialization signals."""
    signals = get_refinement_signals(window_days=window_days, limit=limit * 2)
    created = []
    for s in signals:
        st = s.get("signal_type", "")
        dk = s.get("domain_key", "")
        wk = s.get("workflow_step", "")
        pk = s.get("project_key", "")
        cid = _generate_candidate_id(st, dk or "", wk or "", pk or "")
        existing = get_candidate(cid)
        if existing and existing.get("status") not in ("rejected", "pending_review"):
            continue
        ctype = _candidate_type_from_signal(st, s.get("reason", ""))
        rec_change = s.get("recommended_refinement_action", "")
        now = datetime.now(timezone.utc).isoformat()
        candidate = {
            "tuning_candidate_id": cid,
            "specialization_key": f"{dk or 'general'}_{wk or 'pipeline'}",
            "domain_key": dk or "general",
            "workflow_step": wk or "pipeline",
            "candidate_type": ctype,
            "problem_pattern": s.get("reason", ""),
            "evidence_summary": [s.get("evidence_summary", "")] if s.get("evidence_summary") else [],
            "recommended_tuning_change": rec_change,
            "expected_effect": "Снижение fallback/override, стабильность execution lane",
            "severity": s.get("severity", "low"),
            "status": "pending_review",
            "source_signals": [st],
            "window_days": window_days,
            "created_at": now,
            "reviewed_at": None,
            "reviewer": None,
            "review_notes": None,
            "proposal_id": None,
            "verification_outcome": None,
            "verification_at": None,
            "verification_notes": None,
            "project_key": pk,
        }
        save_candidate(candidate)
        created.append(candidate)
        _audit("tuning_candidate_created", candidate_id=cid, candidate_type=ctype)
    return created


def _audit(event_type: str, **payload: Any) -> None:
    try:
        from app.storage.repositories import get_session_factory, TaskRepository
        from app.shared.audit import log_audit
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, event_type, task_id=None, payload=payload)
    except Exception:
        pass


def get_tuning_candidates(window_days: int = 30, status: Optional[str] = None, limit: int = 20) -> dict[str, Any]:
    """Список tuning candidates."""
    items = list_candidates(status=status, limit=limit)
    return {"items": items, "count": len(items), "window_days": window_days}


def get_tuning_candidate(candidate_id: str) -> Optional[dict[str, Any]]:
    """Один candidate по id."""
    return get_candidate(candidate_id)


def get_specialization_tuning_summary(window_days: int = 30) -> dict[str, Any]:
    """Сводка: pending, accepted, converted, needs verification."""
    pending = list_candidates(status="pending_review", limit=100)
    converted = list_candidates(status="converted", limit=100)
    accepted = list_candidates(status="accepted", limit=100)
    verified = [c for c in list_candidates(limit=200) if c.get("verification_outcome")]
    return {
        "pending_count": len(pending),
        "accepted_count": len(accepted),
        "converted_count": len(converted),
        "verified_count": len(verified),
        "window_days": window_days,
    }


def mark_tuning_candidate_reviewed(
    candidate_id: str,
    decision: str,
    notes: Optional[str] = None,
    reviewer: str = "owner",
) -> Optional[dict[str, Any]]:
    """Review: accept / reject."""
    rec = get_candidate(candidate_id)
    if not rec:
        return None
    decision = (decision or "").strip().lower()
    if decision in ("accept", "approved", "ok"):
        new_status = "accepted"
    elif decision in ("reject", "rejected", "no"):
        new_status = "rejected"
    else:
        return None
    now = datetime.now(timezone.utc).isoformat()
    updated = update_candidate_status(
        candidate_id, new_status,
        reviewer=reviewer, notes=notes, reviewed_at=now,
    )
    _audit("tuning_candidate_reviewed", candidate_id=candidate_id, decision=new_status, reviewer=reviewer)
    return updated


def convert_tuning_candidate_to_proposal(candidate_id: str) -> Optional[dict[str, Any]]:
    """Конвертировать candidate в refinement proposal."""
    rec = get_candidate(candidate_id)
    if not rec or rec.get("status") != "accepted":
        return None
    if rec.get("proposal_id"):
        return get_proposal(rec["proposal_id"])
    backlog = get_refinement_backlog(window_days=rec.get("window_days", 30), limit=50)
    dk = rec.get("domain_key", "")
    wk = rec.get("workflow_step", "")
    pk = rec.get("project_key", "")
    st = (rec.get("source_signals") or [""])[0]
    key = f"{st}:{dk or pk}:{wk}".strip(":")
    matching = [b for b in backlog if b.get("refinement_item_key", "").startswith(st)]
    if not matching:
        matching = [{
            "refinement_item_key": key,
            "item_type": st,
            "domain_key": dk or None,
            "workflow_step": wk or None,
            "project_key": pk,
            "severity": rec.get("severity", "low"),
            "reason": rec.get("problem_pattern", ""),
            "recommended_change": rec.get("recommended_tuning_change", ""),
            "evidence_summary": " ".join(rec.get("evidence_summary", [])),
        }]
    b = matching[0]
    proposal_id = f"rp_tc_{candidate_id[:20]}_{abs(hash(key)) % 10000}"
    now = datetime.now(timezone.utc).isoformat()
    ptype = "expand_specialization_profile" if "fallback" in (rec.get("candidate_type") or "").lower() else "adjust_routing_keywords"
    proposal = {
        "proposal_id": proposal_id,
        "proposal_type": ptype,
        "target_layer": "specializations",
        "target_key": f"{dk or 'general'}:{wk or 'pipeline'}",
        "reason": rec.get("problem_pattern", ""),
        "evidence_summary": " ".join(rec.get("evidence_summary", [])),
        "recommended_change": rec.get("recommended_tuning_change", ""),
        "source_signals": rec.get("source_signals", []) + [f"tuning_candidate:{candidate_id}"],
        "severity": rec.get("severity", "low"),
        "status": "accepted",
        "created_at": now,
        "reviewed_at": now,
        "source_tuning_candidate_id": candidate_id,
    }
    save_proposal(proposal)
    update_candidate_status(candidate_id, "converted", proposal_id=proposal_id)
    _audit("tuning_candidate_converted", candidate_id=candidate_id, proposal_id=proposal_id)
    return proposal


def mark_tuning_candidate_verified(
    candidate_id: str,
    outcome: str,
    notes: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Verification: improved, unchanged, worse, insufficient_data."""
    rec = get_candidate(candidate_id)
    if not rec:
        return None
    outcome = (outcome or "").strip().lower()
    if outcome not in ("improved", "unchanged", "worse", "insufficient_data"):
        return None
    now = datetime.now(timezone.utc).isoformat()
    updated = update_candidate_status(
        candidate_id, "verified",
        verification_outcome=outcome,
        verification_at=now,
        verification_notes=notes,
    )
    _audit("tuning_candidate_verified", candidate_id=candidate_id, outcome=outcome)
    return updated
