# app/services/collaboration_execution_store.py — Phase 11.4: persist collaboration executions
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List, Optional

_EXEC_PATH = Path(__file__).resolve().parents[1] / "data" / "collaboration_executions.json"

_CLOSED = frozenset({"closed", "cancelled"})


def _path() -> Path:
    return Path(os.environ.get("COLLABORATION_EXECUTIONS_PATH", str(_EXEC_PATH)))


def _load() -> dict[str, Any]:
    p = _path()
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        return {"executions": {}}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"executions": {}}


def _save(data: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_execution(execution_id: str) -> Optional[dict[str, Any]]:
    data = _load()
    return (data.get("executions") or {}).get(execution_id)


def save_execution(rec: dict[str, Any]) -> None:
    eid = rec.get("execution_id")
    if not eid:
        return
    data = _load()
    data.setdefault("executions", {})[eid] = rec
    _save(data)


def list_executions(status: Optional[str] = None, limit: int = 100) -> List[dict[str, Any]]:
    data = _load()
    items = list((data.get("executions") or {}).values())
    items = [i for i in items if isinstance(i, dict)]
    if status:
        items = [i for i in items if i.get("execution_status") == status]
    items.sort(key=lambda x: (x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return items[:limit]


def find_open_by_fingerprint(suggestion_fingerprint: str) -> Optional[dict[str, Any]]:
    if not suggestion_fingerprint:
        return None
    for rec in list_executions(limit=500):
        if rec.get("suggestion_fingerprint") != suggestion_fingerprint:
            continue
        if (rec.get("execution_status") or "") in _CLOSED:
            continue
        return rec
    return None


def count_pending_for_subject(subject_type: Optional[str], subject_key: Optional[str]) -> int:
    if not subject_type or subject_key is None:
        return 0
    n = 0
    for rec in list_executions(limit=500):
        if rec.get("subject_type") != subject_type or str(rec.get("subject_key")) != str(subject_key):
            continue
        if (rec.get("execution_status") or "") in _CLOSED:
            continue
        n += 1
    return n
