# app/services/collaboration_execution.py — Phase 11.4: collaboration execution layer
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from app.services.collaboration_execution_store import (
    find_open_by_fingerprint,
    get_execution,
    list_executions as _list_executions_store,
    save_execution,
)
from app.services.action_center import can_execute_action, execute_action_for_collaboration_execution

_CLOSED = frozenset({"closed", "cancelled"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _map_suggestion_to_execution_type(suggestion: dict[str, Any]) -> str:
    st = (suggestion.get("suggestion_type") or "").lower()
    if "approval" in st or "resolution" in st:
        return "request_decision_resolution"
    if "runtime" in st or "escalation" in st:
        return "escalate_runtime_issue"
    if "handoff" in st:
        return "mark_handoff_followup"
    if "owner_attention" in st or "attention" in st:
        return "request_owner_attention"
    if "rework" in st:
        return "request_review"
    return "acknowledge_collaboration_gap"


def _validate_safe_action_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    if can_execute_action("owner", key):
        return key
    return None


def build_execution_from_suggestion(suggestion: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Создать execution из suggestion (dict) или вернуть открытый с тем же fingerprint.
    """
    if not suggestion or not isinstance(suggestion, dict):
        return None
    fp = suggestion.get("suggestion_fingerprint")
    if not fp:
        from app.services.collaboration_action_suggestions import compute_suggestion_fingerprint

        fp = compute_suggestion_fingerprint(suggestion)
    existing = find_open_by_fingerprint(fp)
    if existing:
        return existing

    raw_safe = suggestion.get("safe_action_available")
    safe_key = _validate_safe_action_key(raw_safe)
    eid = "ce_" + uuid.uuid4().hex[:12]
    ts = _now()
    snap: dict[str, Any] = {}
    for k in (
        "suggestion_type", "subject_type", "subject_key", "headline", "reason",
        "recommended_next_step", "urgency", "safe_action_available", "evidence_summary",
    ):
        v = suggestion.get(k)
        if v is not None:
            snap[k] = v
    rec = {
        "execution_id": eid,
        "suggestion_id": suggestion.get("suggestion_id"),
        "suggestion_fingerprint": fp,
        "suggestion_snapshot": snap,
        "execution_type": _map_suggestion_to_execution_type(suggestion),
        "subject_type": suggestion.get("subject_type") or "portfolio",
        "subject_key": str(suggestion.get("subject_key") or ""),
        "source_role": suggestion.get("source_role") or "system",
        "target_role": suggestion.get("target_role") or "owner",
        "execution_status": "available",
        "execution_reason": suggestion.get("reason") or suggestion.get("headline") or "Collaboration execution",
        "safe_action_key": safe_key,
        "last_action_result": None,
        "created_at": ts,
        "updated_at": ts,
        "closed_at": None,
        "closure_reason": None,
        "actor": None,
    }
    save_execution(rec)
    _audit(
        "collaboration_execution_created",
        execution_id=eid,
        suggestion_fingerprint=fp,
        execution_status="available",
        safe_action_key=safe_key,
    )
    return rec


def trigger_collaboration_execution(
    execution_id: str,
    actor: Optional[str] = None,
    *,
    run_safe_action: bool = True,
    role: str = "owner",
) -> Optional[dict[str, Any]]:
    """Explicit trigger; опционально вызывает safe action из action center."""
    rec = get_execution(execution_id)
    if not rec:
        return None
    if (rec.get("execution_status") or "") in _CLOSED:
        return None

    actor = actor or "owner"
    rec = dict(rec)
    rec["execution_status"] = "triggered"
    rec["updated_at"] = _now()
    rec["actor"] = actor
    save_execution(rec)
    _audit("collaboration_execution_triggered", execution_id=execution_id, actor=actor)

    safe_key = rec.get("safe_action_key")
    if run_safe_action and safe_key:
        result = execute_action_for_collaboration_execution(
            safe_key,
            role=role,
            execution_id=execution_id,
            actor=actor,
        )
        action_id = result.get("action_id")
        _audit(
            "collaboration_execution_action_linked",
            execution_id=execution_id,
            safe_action_key=safe_key,
            action_id=action_id,
            action_success=result.get("success"),
        )
        rec["last_action_result"] = (result.get("result_summary") or "")[:500]
        if result.get("success"):
            rec["execution_status"] = "acknowledged"
            _audit(
                "collaboration_execution_acknowledged",
                execution_id=execution_id,
                action_id=action_id,
            )
        else:
            rec["execution_status"] = "in_progress"
        rec["updated_at"] = _now()
        save_execution(rec)
    elif not safe_key:
        rec["execution_status"] = "in_progress"
        rec["updated_at"] = _now()
        save_execution(rec)

    return get_execution(execution_id)


def mark_collaboration_execution_closed(
    execution_id: str,
    actor: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    rec = get_execution(execution_id)
    if not rec:
        return None
    rec = dict(rec)
    rec["execution_status"] = "closed"
    rec["closed_at"] = _now()
    rec["closure_reason"] = reason or "closed_by_owner"
    rec["actor"] = actor or rec.get("actor")
    rec["updated_at"] = _now()
    save_execution(rec)
    _audit(
        "collaboration_execution_closed",
        execution_id=execution_id,
        closure_reason=rec["closure_reason"],
        actor=actor,
    )
    try:
        from app.services.collaboration_outcomes import record_collaboration_outcome_baseline_on_close

        record_collaboration_outcome_baseline_on_close(execution_id)
    except Exception:
        pass
    return rec


def mark_collaboration_execution_cancelled(
    execution_id: str,
    actor: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    rec = get_execution(execution_id)
    if not rec:
        return None
    rec = dict(rec)
    rec["execution_status"] = "cancelled"
    rec["closed_at"] = _now()
    rec["closure_reason"] = reason or "cancelled"
    rec["updated_at"] = _now()
    save_execution(rec)
    _audit("collaboration_execution_closed", execution_id=execution_id, closure_reason=rec["closure_reason"], cancelled=True)
    return rec


def get_collaboration_execution_summary(window_days: int = 7) -> dict[str, Any]:
    items = _list_executions_store(limit=300)
    # window filter по created_at (грубо)
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    recent = []
    for i in items:
        try:
            ca = datetime.fromisoformat((i.get("created_at") or "1970-01-01").replace("Z", "+00:00"))
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            if ca >= cutoff:
                recent.append(i)
        except Exception:
            recent.append(i)

    open_status = {"available", "triggered", "in_progress", "acknowledged"}
    pending = [x for x in recent if (x.get("execution_status") or "") in open_status]
    closed = [x for x in recent if (x.get("execution_status") or "") == "closed"]
    return {
        "window_days": window_days,
        "pending_count": len(pending),
        "closed_count": len(closed),
        "total_recent": len(recent),
        "explainable": True,
    }


def get_pending_collaboration_executions(window_days: int = 7, limit: int = 50) -> dict[str, Any]:
    summary = get_collaboration_execution_summary(window_days=window_days)
    open_status = {"available", "triggered", "in_progress", "acknowledged"}
    items = [x for x in _list_executions_store(limit=200) if (x.get("execution_status") or "") in open_status]
    return {"items": items[:limit], "count": len(items[:limit]), "summary": summary}


def get_collaboration_execution(execution_id: str) -> Optional[dict[str, Any]]:
    return get_execution(execution_id)


def list_collaboration_executions(status: Optional[str] = None, limit: int = 100) -> List[dict[str, Any]]:
    return _list_executions_store(status=status, limit=limit)
