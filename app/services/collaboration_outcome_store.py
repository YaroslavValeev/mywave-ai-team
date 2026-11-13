# app/services/collaboration_outcome_store.py — Phase 11.5: persist collaboration execution outcomes
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List, Optional

_OUTCOMES_PATH = Path(__file__).resolve().parents[1] / "data" / "collaboration_outcomes.json"


def _path() -> Path:
    return Path(os.environ.get("COLLABORATION_OUTCOMES_PATH", str(_OUTCOMES_PATH)))


def _load() -> dict[str, Any]:
    p = _path()
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        return {"outcomes": {}}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"outcomes": {}}


def _save(data: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def outcome_id_for_execution(execution_id: str) -> str:
    return f"co_{execution_id}"


def get_outcome_record(outcome_id: str) -> Optional[dict[str, Any]]:
    data = _load()
    return (data.get("outcomes") or {}).get(outcome_id)


def get_outcome_by_execution(execution_id: str) -> Optional[dict[str, Any]]:
    return get_outcome_record(outcome_id_for_execution(execution_id))


def save_outcome_record(rec: dict[str, Any]) -> None:
    oid = rec.get("outcome_id")
    if not oid:
        return
    data = _load()
    data.setdefault("outcomes", {})[oid] = rec
    _save(data)


def list_outcome_records(limit: int = 200) -> List[dict[str, Any]]:
    data = _load()
    items = list((data.get("outcomes") or {}).values())
    items = [i for i in items if isinstance(i, dict)]
    items.sort(key=lambda x: (x.get("measured_at") or x.get("baseline_captured_at") or ""), reverse=True)
    return items[:limit]


def merge_outcome(outcome_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    existing = get_outcome_record(outcome_id) or {"outcome_id": outcome_id}
    merged = {**existing, **{k: v for k, v in updates.items() if v is not None}}
    save_outcome_record(merged)
    return merged
