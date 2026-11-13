# app/services/intervention_acceptance.py — Phase 12.3: owner acceptance loop
"""Запись и чтение owner response (defer/accept) для interventions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.storage.repositories import get_session_factory, TaskRepository
from app.shared.audit import log_audit

_EVENT_TYPE = "intervention_owner_response"
_DEFAULT_DEFER_HOURS = 24


def _parse_intervention_id(intervention_id: str) -> tuple[str, str]:
    """Parse iv_{scope_type}_{scope_key}_{idx} -> (scope_type, scope_key)."""
    parts = (intervention_id or "").split("_")
    if len(parts) >= 4:
        return parts[1], "" if parts[2] == "x" else parts[2]
    return "portfolio", ""


def record_intervention_response(
    intervention_id: str,
    scope_type: Optional[str] = None,
    scope_key: Optional[str] = None,
    response: str = "deferred",
    actor: str = "owner",
    defer_hours: Optional[int] = None,
) -> dict[str, Any]:
    """
    Записать ответ owner: deferred или accepted.
    scope_type/scope_key опциональны — парсятся из intervention_id если не заданы.
    Returns: {success, intervention_id, response, defer_hours}.
    """
    response = (response or "").strip().lower()
    if response not in ("deferred", "accepted"):
        return {"success": False, "error": "response must be deferred or accepted"}

    if scope_type is None or scope_key is None:
        scope_type, scope_key = _parse_intervention_id(intervention_id)

    hours = defer_hours if defer_hours is not None else _DEFAULT_DEFER_HOURS
    payload = {
        "intervention_id": intervention_id,
        "scope_type": scope_type,
        "scope_key": scope_key,
        "response": response,
        "actor": actor,
        "defer_hours": hours,
    }
    try:
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, _EVENT_TYPE, task_id=None, payload=payload)
        return {"success": True, "intervention_id": intervention_id, "response": response, "defer_hours": hours}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_recently_deferred_ids(hours: int = 24) -> set[str]:
    """
    Вернуть intervention_id, отложенные в течение последних hours часов.
    Используется при построении do_now — исключить их из топа.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result: set[str] = set()
    try:
        from app.storage.models import AuditEvent

        Session = get_session_factory()
        with Session() as session:
            events = (
                session.query(AuditEvent)
                .filter(AuditEvent.event_type == _EVENT_TYPE)
                .filter(AuditEvent.created_at >= cutoff)
                .all()
            )
            for ev in events:
                p = ev.payload_json or {}
                if p.get("response") == "deferred":
                    iid = p.get("intervention_id")
                    if iid:
                        result.add(str(iid))
    except Exception:
        pass
    return result
