from __future__ import annotations

from collections import defaultdict
import logging
from typing import Any

from app.business_execution.growth_engine import growth_override_allowed
logger = logging.getLogger(__name__)


def _normalize_pack_type(v: str | None) -> str:
    t = str(v or "").strip() or "generic_pack"
    return t


def _is_success(action: dict[str, Any], snapshots: list[dict[str, Any]]) -> bool:
    status = str(action.get("status") or "")
    fb = str(action.get("owner_feedback") or "").lower()
    result_summary = str(action.get("result_summary") or "").strip()
    has_snapshot_value = any(str(s.get("result_value") or "").strip() for s in snapshots)
    if status == "done":
        return True
    if any(x in fb for x in ("сработ", "полез", "выполн")):
        return True
    return bool(result_summary or has_snapshot_value)


def _is_failure(action: dict[str, Any], snapshots: list[dict[str, Any]], pack_type: str) -> bool:
    status = str(action.get("status") or "")
    fb = str(action.get("owner_feedback") or "").lower()
    if "не сработ" in fb:
        return True
    if status == "skipped":
        if "не делал" in fb or pack_type != "generic_pack":
            return True
    if status in {"done", "skipped"}:
        has_signal = bool(str(action.get("result_summary") or "").strip()) or any(
            str(s.get("result_value") or "").strip() for s in snapshots
        )
        if not has_signal:
            return True
    return False


def record_pack_feedback(pack_type: str, feedback: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    action = feedback if isinstance(feedback, dict) else {}
    snapshots = [outcome] if isinstance(outcome, dict) else []
    success = _is_success(action, snapshots)
    failure = _is_failure(action, snapshots, pack_type)
    status = str(action.get("status") or "")
    started = bool(action.get("started_at") or status in {"in_progress", "done", "skipped"})
    completed = status in {"done", "skipped"}
    return {
        "pack_type": _normalize_pack_type(pack_type),
        "started": started,
        "completed": completed,
        "success": success,
        "failure": failure,
        "actionability": float(action.get("actionability", 0) or 0),
        "result_probability": float(action.get("result_probability", 0) or 0),
    }


def _iter_rows(tasks: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for t in tasks:
        ba = getattr(t, "business_action_json", None)
        if not isinstance(ba, dict):
            continue
        pack = ba.get("execution_pack") if isinstance(ba.get("execution_pack"), dict) else {}
        action = ba.get("action_instance") if isinstance(ba.get("action_instance"), dict) else {}
        score = ba.get("execution_scoring") if isinstance(ba.get("execution_scoring"), dict) else {}
        snaps_raw = ba.get("result_snapshots") if isinstance(ba.get("result_snapshots"), list) else []
        snapshots = [s for s in snaps_raw if isinstance(s, dict)]
        if not pack:
            continue

        pack_type = _normalize_pack_type(pack.get("pack_type") or action.get("action_type"))
        status = str(action.get("status") or "pending")
        generated = 1
        started = bool(action.get("started_at") or status in {"in_progress", "done", "skipped"})
        completed = status in {"done", "skipped"}
        success = _is_success(action, snapshots)
        failure = _is_failure(action, snapshots, pack_type)

        rows.append(
            {
                "pack_type": pack_type,
                "generated": generated,
                "started": 1 if started else 0,
                "completed": 1 if completed else 0,
                "success": 1 if success else 0,
                "failure": 1 if failure else 0,
                "actionability": float(score.get("actionability") or 0),
                "result_probability": float(score.get("result_probability") or 0),
                "notes": str(action.get("owner_feedback") or "")[:300],
            }
        )
    return rows


def aggregate_pack_performance(pack_type: str, tasks: list[Any]) -> dict[str, Any]:
    pt = _normalize_pack_type(pack_type)
    grouped = [r for r in _iter_rows(tasks) if r["pack_type"] == pt]
    total = len(grouped)
    started = sum(r["started"] for r in grouped)
    completed = sum(r["completed"] for r in grouped)
    useful = sum(r["success"] for r in grouped)
    useless = sum(r["failure"] for r in grouped)
    success_rate = round(useful / total, 2) if total else 0.0
    failure_rate = round(useless / total, 2) if total else 0.0
    avg_actionability = round(sum(r["actionability"] for r in grouped) / total, 2) if total else 0.0
    avg_result_probability = round(sum(r["result_probability"] for r in grouped) / total, 2) if total else 0.0

    weak_reason = ""
    if failure_rate >= 0.5 and pt == "partner_outreach_pack":
        weak_reason = "Обычно не хватает реальных контактов."
    elif failure_rate >= 0.5:
        weak_reason = "Высокая доля негативного или пустого результата."

    notes_for_builder = weak_reason or "Сигнал пока недостаточный."
    return {
        "pack_type": pt,
        "total_generated": total,
        "total_started": started,
        "total_completed": completed,
        "useful_count": useful,
        "useless_count": useless,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "avg_actionability": avg_actionability,
        "avg_result_probability": avg_result_probability,
        "notes_for_builder": notes_for_builder,
    }


def aggregate_all_pack_performance(tasks: list[Any]) -> dict[str, dict[str, Any]]:
    all_rows = _iter_rows(tasks)
    pack_types = sorted({r["pack_type"] for r in all_rows})
    return {pt: aggregate_pack_performance(pt, tasks) for pt in pack_types}


def compute_pack_scores(pack_type: str, tasks: list[Any]) -> dict[str, Any]:
    perf = aggregate_pack_performance(pack_type, tasks)
    confidence = perf["total_generated"]
    reliability = "низкая"
    if confidence >= 8 and perf["success_rate"] >= 0.55:
        reliability = "высокая"
    elif confidence >= 4 and perf["success_rate"] >= 0.35:
        reliability = "средняя"
    return {
        "pack_type": perf["pack_type"],
        "confidence": confidence,
        "reliability": reliability,
        "historical_usefulness": perf["success_rate"],
        "historical_failure": perf["failure_rate"],
    }


def build_pack_learning_hints(pack_type: str, tasks: list[Any]) -> dict[str, Any]:
    perf = aggregate_pack_performance(pack_type, tasks)
    scores = compute_pack_scores(pack_type, tasks)

    mode = "normal_generate"
    if perf["failure_rate"] >= 0.5 and perf["total_generated"] >= 3:
        mode = "clarify_before_generate"
    elif perf["success_rate"] >= 0.6 and perf["total_generated"] >= 3:
        mode = "preferred_template"

    return {
        "pack_type": perf["pack_type"],
        "historical_success_rate": perf["success_rate"],
        "historical_failure_rate": perf["failure_rate"],
        "learning_hint": perf["notes_for_builder"],
        "recommended_mode": mode,
        "confidence": scores["confidence"],
        "reliability": scores["reliability"],
    }


def apply_learning_to_pack_builder(context: dict[str, Any], hints_by_type: dict[str, dict[str, Any]]) -> dict[str, Any]:
    base_pack_type = _normalize_pack_type(str(context.get("base_pack_type") or "generic_pack"))
    hint = hints_by_type.get(base_pack_type) or {}
    selected = base_pack_type
    warning = ""

    mode = str(hint.get("recommended_mode") or "normal_generate")
    if mode == "clarify_before_generate":
        selected = "generic_pack"
        warning = str(hint.get("learning_hint") or "Недостаточно входных данных, сначала уточните контекст.")
    elif mode == "preferred_template":
        selected = base_pack_type

    base_priority = float(hint.get("priority_score") or 0)
    ranked = [
        (pt, float(h.get("priority_score") or 0), str(h.get("recommended_mode") or ""))
        for pt, h in hints_by_type.items()
        if not str(pt).startswith("__")
    ]
    ranked.sort(key=lambda x: x[1], reverse=True)
    if ranked:
        best_pt, best_priority, best_mode = ranked[0]
        base_gen = int((hints_by_type.get(base_pack_type) or {}).get("growth_generated") or 0)
        best_gen = int((hints_by_type.get(best_pt) or {}).get("growth_generated") or 0)
        if (
            best_pt != base_pack_type
            and mode != "clarify_before_generate"
            and growth_override_allowed(
                base_priority=base_priority,
                best_priority=best_priority,
                base_generated=base_gen,
                best_generated=best_gen,
            )
        ):
            selected = best_pt
            warning = (
                f"Growth bias: {base_pack_type} ослаблен, выбран {best_pt} "
                f"(priority {best_priority} vs {base_priority}, n={best_gen}/{base_gen})."
            )
            mode = "growth_override"
            logger.info(
                "growth_override_applied base_pack=%s selected_pack=%s base_priority=%.3f best_priority=%.3f base_n=%s best_n=%s",
                base_pack_type,
                best_pt,
                base_priority,
                best_priority,
                base_gen,
                best_gen,
            )

    return {
        "base_pack_type": base_pack_type,
        "selected_pack_type": selected,
        "learning_hint": str(hint.get("learning_hint") or ""),
        "recommended_mode": mode,
        "warning": warning,
        "confidence": int(hint.get("confidence") or 0),
        "reliability": str(hint.get("reliability") or "низкая"),
        "historical_success_rate": float(hint.get("historical_success_rate") or 0),
        "historical_failure_rate": float(hint.get("historical_failure_rate") or 0),
    }
