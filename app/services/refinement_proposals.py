# app/services/refinement_proposals.py — Phase 10.6: refinement proposal generation and lifecycle
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from app.services.domain_specialization_analytics import get_refinement_backlog
from app.services.refinement_proposal_store import (
    get_proposal,
    list_proposals,
    save_proposal,
    update_proposal_status,
)


def _proposal_type_from_item_type(item_type: str, recommended_change: str) -> str:
    if "specialization" in (recommended_change or "").lower() or "profile" in (recommended_change or "").lower():
        return "add_specialization_profile" if "add" in (recommended_change or "").lower() else "expand_specialization_profile"
    if "routing" in (recommended_change or "").lower() or "keywords" in (recommended_change or "").lower():
        return "adjust_routing_keywords"
    if "alias" in (recommended_change or "").lower():
        return "add_alias"
    if "override" in (recommended_change or "").lower() or "причины" in (recommended_change or "").lower():
        return "review_domain_mapping"
    return "tighten_fallback_rule"


def _target_layer_from_type(proposal_type: str) -> str:
    if "specialization" in proposal_type:
        return "specializations"
    if proposal_type in ("adjust_routing_keywords", "add_alias", "review_domain_mapping"):
        return "domain_registry"
    return "domain_registry"


def generate_refinement_proposals(window_days: int = 30, limit: int = 20) -> List[dict[str, Any]]:
    """Создать proposals из refinement backlog; сохранить в store; вернуть список созданных."""
    backlog = get_refinement_backlog(window_days=window_days, limit=limit)
    created = []
    for b in backlog:
        key = b.get("refinement_item_key", "")
        if not key:
            continue
        proposal_id = f"rp_{key.replace(':', '_')[:40]}" + "_" + str(abs(hash(key)) % 100000)
        existing = get_proposal(proposal_id)
        if existing and existing.get("status") not in ("rejected", "proposed"):
            continue
        now = datetime.now(timezone.utc).isoformat()
        rec_change = b.get("recommended_change", "")
        ptype = _proposal_type_from_item_type(b.get("item_type", ""), rec_change)
        target_layer = _target_layer_from_type(ptype)
        target_key = b.get("domain_key") or b.get("project_key") or ""
        if b.get("workflow_step"):
            target_key = f"{target_key}:{b.get('workflow_step')}".strip(":")
        proposal = {
            "proposal_id": proposal_id,
            "proposal_type": ptype,
            "target_layer": target_layer,
            "target_key": target_key,
            "reason": b.get("reason", ""),
            "evidence_summary": b.get("evidence_summary", ""),
            "recommended_change": rec_change,
            "source_signals": [b.get("item_type"), b.get("refinement_item_key")],
            "severity": b.get("severity", "low"),
            "status": "proposed",
            "created_at": now,
            "reviewed_at": None,
            "applied_at": None,
            "reviewer": None,
            "notes": None,
            "domain_key": b.get("domain_key"),
            "workflow_step": b.get("workflow_step"),
            "project_key": b.get("project_key"),
        }
        save_proposal(proposal)
        created.append(proposal)
        _audit("refinement_proposal_created", proposal_id=proposal_id, proposal_type=ptype, target_layer=target_layer, target_key=target_key)
    return created


def _audit(event_type: str, proposal_id: str, **payload: Any) -> None:
    try:
        from app.storage.repositories import get_session_factory, TaskRepository
        from app.shared.audit import log_audit
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, event_type, task_id=None, payload={"proposal_id": proposal_id, **payload})
    except Exception:
        pass


def list_refinement_proposals(status: Optional[str] = None, limit: int = 50) -> List[dict[str, Any]]:
    """Список proposals с опциональным фильтром по status."""
    return list_proposals(status=status, limit=limit)


def get_refinement_proposal(proposal_id: str) -> Optional[dict[str, Any]]:
    """Один proposal по id."""
    return get_proposal(proposal_id)


def review_refinement_proposal(
    proposal_id: str,
    decision: str,
    reviewer: str = "owner",
    notes: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Ревью: accept или reject. Обновляет status, reviewed_at, reviewer, notes."""
    rec = get_proposal(proposal_id)
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
    updated = update_proposal_status(proposal_id, new_status, reviewer=reviewer, notes=notes, reviewed_at=now)
    if updated:
        _audit("refinement_proposal_reviewed", proposal_id=proposal_id, decision=new_status, reviewer=reviewer)
        if new_status == "accepted":
            _audit("refinement_proposal_accepted", proposal_id=proposal_id, reviewer=reviewer)
        else:
            _audit("refinement_proposal_rejected", proposal_id=proposal_id, reviewer=reviewer, notes=notes or "")
    return updated


def mark_refinement_proposal_applied(
    proposal_id: str,
    reviewer: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Отметить proposal как применённое (фактическое изменение или ручное по экспорту)."""
    rec = get_proposal(proposal_id)
    if not rec:
        return None
    if rec.get("status") != "accepted":
        return None
    now = datetime.now(timezone.utc).isoformat()
    updated = update_proposal_status(proposal_id, "applied", reviewer=reviewer or "owner", notes=notes, applied_at=now)
    if updated:
        _audit("refinement_proposal_applied", proposal_id=proposal_id, reviewer=reviewer or "owner", notes=notes or "")
    return updated
