# app/services/refinement_proposal_store.py — Phase 10.6: persist refinement proposals
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List, Optional

_PROPOSALS_PATH = Path(__file__).resolve().parents[1] / "data" / "refinement_proposals.json"


def _path() -> Path:
    return Path(os.environ.get("REFINEMENT_PROPOSALS_PATH", str(_PROPOSALS_PATH)))


def _load() -> dict[str, Any]:
    p = _path()
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        return {"proposals": {}}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"proposals": {}}


def _save(data: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_proposals(status: Optional[str] = None, limit: int = 50) -> List[dict[str, Any]]:
    """Список proposals; при status не None — фильтр по status."""
    data = _load()
    items = list((data.get("proposals") or {}).values())
    items = [i for i in items if isinstance(i, dict)]
    if status:
        items = [i for i in items if i.get("status") == status]
    items.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)
    return items[:limit]


def get_proposal(proposal_id: str) -> Optional[dict[str, Any]]:
    """Один proposal по id."""
    data = _load()
    return (data.get("proposals") or {}).get(proposal_id)


def save_proposal(proposal: dict[str, Any]) -> None:
    """Сохранить или обновить proposal (по proposal_id)."""
    pid = proposal.get("proposal_id")
    if not pid:
        return
    data = _load()
    data.setdefault("proposals", {})[pid] = proposal
    _save(data)


def update_proposal_status(
    proposal_id: str,
    status: str,
    *,
    reviewer: Optional[str] = None,
    notes: Optional[str] = None,
    reviewed_at: Optional[str] = None,
    applied_at: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Обновить статус и опционально reviewer, notes, timestamps."""
    data = _load()
    proposals = data.get("proposals") or {}
    rec = proposals.get(proposal_id)
    if not rec:
        return None
    rec = dict(rec)
    rec["status"] = status
    if reviewer is not None:
        rec["reviewer"] = reviewer
    if notes is not None:
        rec["notes"] = notes
    if reviewed_at is not None:
        rec["reviewed_at"] = reviewed_at
    if applied_at is not None:
        rec["applied_at"] = applied_at
    proposals[proposal_id] = rec
    _save(data)
    return rec
