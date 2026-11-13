# app/services/agent_tuning_store.py — Phase 11.2: persist tuning candidates
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List, Optional

_TUNING_PATH = Path(__file__).resolve().parents[1] / "data" / "agent_tuning_candidates.json"


def _path() -> Path:
    return Path(os.environ.get("AGENT_TUNING_CANDIDATES_PATH", str(_TUNING_PATH)))


def _load() -> dict[str, Any]:
    p = _path()
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        return {"candidates": {}}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"candidates": {}}


def _save(data: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_candidates(status: Optional[str] = None, limit: int = 50) -> List[dict[str, Any]]:
    """Список tuning candidates; при status — фильтр."""
    data = _load()
    items = list((data.get("candidates") or {}).values())
    items = [i for i in items if isinstance(i, dict)]
    if status:
        items = [i for i in items if i.get("status") == status]
    items.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)
    return items[:limit]


def get_candidate(candidate_id: str) -> Optional[dict[str, Any]]:
    """Один candidate по id."""
    data = _load()
    return (data.get("candidates") or {}).get(candidate_id)


def save_candidate(candidate: dict[str, Any]) -> None:
    """Сохранить или обновить candidate."""
    cid = candidate.get("tuning_candidate_id")
    if not cid:
        return
    data = _load()
    data.setdefault("candidates", {})[cid] = candidate
    _save(data)


def update_candidate_status(
    candidate_id: str,
    status: str,
    *,
    reviewer: Optional[str] = None,
    notes: Optional[str] = None,
    reviewed_at: Optional[str] = None,
    proposal_id: Optional[str] = None,
    verification_outcome: Optional[str] = None,
    verification_at: Optional[str] = None,
    verification_notes: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Обновить статус и связанные поля."""
    data = _load()
    candidates = data.get("candidates") or {}
    rec = candidates.get(candidate_id)
    if not rec:
        return None
    rec = dict(rec)
    rec["status"] = status
    if reviewer is not None:
        rec["reviewer"] = reviewer
    if notes is not None:
        rec["review_notes"] = notes
    if reviewed_at is not None:
        rec["reviewed_at"] = reviewed_at
    if proposal_id is not None:
        rec["proposal_id"] = proposal_id
    if verification_outcome is not None:
        rec["verification_outcome"] = verification_outcome
    if verification_at is not None:
        rec["verification_at"] = verification_at
    if verification_notes is not None:
        rec["verification_notes"] = verification_notes
    candidates[candidate_id] = rec
    _save(data)
    return rec
