from __future__ import annotations

import time
from typing import Any, Literal

from app.business_execution.learning_hooks import (
    aggregate_pack_performance,
    build_pack_learning_hints,
    compute_pack_scores,
)
from app.business_execution.growth_engine import build_growth_insight, compute_pack_performance_with_revenue
from app.business_execution.pack_builder import build_pack, choose_pack_type
from app.business_execution.schemas import ExecutionContext, ExecutionPack

ActionStatus = Literal["pending", "in_progress", "done", "skipped"]


def _learning_hints_for_context(ctx: ExecutionContext, all_tasks: list[Any] | None) -> dict[str, dict[str, Any]]:
    if not all_tasks:
        return {}
    perf = compute_pack_performance_with_revenue(all_tasks)
    hints: dict[str, dict[str, Any]] = {}
    for pt in [
        "offer_pack",
        "partner_outreach_pack",
        "content_pack",
        "landing_pack",
        "launch_plan_pack",
        "generic_pack",
    ]:
        h = build_pack_learning_hints(pt, all_tasks)
        h["priority_score"] = float((perf.get(pt) or {}).get("priority_score") or 0)
        g = int((perf.get(pt) or {}).get("generated") or 0)
        h["growth_generated"] = g
        h["growth_confidence"] = round(min(1.0, g / 8.0), 4)
        hints[pt] = h
    base = choose_pack_type(ctx)
    if base not in hints:
        h = build_pack_learning_hints(base, all_tasks)
        h["priority_score"] = float((perf.get(base) or {}).get("priority_score") or 0)
        g = int((perf.get(base) or {}).get("generated") or 0)
        h["growth_generated"] = g
        h["growth_confidence"] = round(min(1.0, g / 8.0), 4)
        hints[base] = h
    return hints


def pack_learning_quality(pack_type: str, all_tasks: list[Any] | None) -> dict[str, Any]:
    if not all_tasks:
        return {
            "pack_type": pack_type or "generic_pack",
            "historical_usefulness": 0.0,
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "confidence": 0,
            "reliability": "низкая",
            "notes_for_builder": "Сигнал пока недостаточный.",
        }
    perf = aggregate_pack_performance(pack_type, all_tasks)
    score = compute_pack_scores(pack_type, all_tasks)
    growth = compute_pack_performance_with_revenue(all_tasks).get(pack_type, {})
    return {
        "pack_type": perf["pack_type"],
        "historical_usefulness": perf["success_rate"],
        "success_rate": perf["success_rate"],
        "failure_rate": perf["failure_rate"],
        "confidence": score["confidence"],
        "reliability": score["reliability"],
        "notes_for_builder": perf["notes_for_builder"],
        "priority_score": float(growth.get("priority_score") or 0),
        "revenue_signal": round(float(growth.get("revenue", 0) or 0), 2),
    }


def build_execution_pack_from_gm(
    *,
    next_business_step: str,
    business_value_hint: str = "",
    owner_workstream: str = "",
    business_type: str = "",
    business_unit: str = "",
    workflow_template: str = "",
    expected_outcome: str = "",
    project_name: str = "",
    project_goal: str = "",
    project_stage: str = "",
    owner_text: str = "",
    task_id: int | None = None,
    all_tasks: list[Any] | None = None,
) -> ExecutionPack | None:
    if not (next_business_step or "").strip():
        return None
    ctx = ExecutionContext(
        next_business_step=next_business_step,
        business_value_hint=business_value_hint,
        owner_workstream=owner_workstream,
        business_type=business_type,
        business_unit=business_unit,
        workflow_template=workflow_template,
        expected_outcome=expected_outcome,
        project_name=project_name,
        project_goal=project_goal,
        project_stage=project_stage,
        owner_text=owner_text,
        task_id=task_id,
    )
    learning_hints = _learning_hints_for_context(ctx, all_tasks)
    return build_pack(ctx, learning_hints=learning_hints)


def ensure_execution_pack_for_task(task, project=None, all_tasks: list[Any] | None = None) -> ExecutionPack | None:
    ctx = ExecutionContext.from_task(task, project)
    if not ctx.next_business_step:
        return None
    learning_hints = _learning_hints_for_context(ctx, all_tasks)
    return build_pack(ctx, learning_hints=learning_hints)


def execution_scoring(pack: dict[str, Any]) -> dict[str, float]:
    ready = pack.get("ready_steps") if isinstance(pack.get("ready_steps"), list) else []
    has_action = 1.0 if pack.get("action_title") else 0.0
    has_how = 1.0 if pack.get("how_to_execute") else 0.0
    has_result = 1.0 if pack.get("expected_result") else 0.0
    specificity = min(1.0, (len(ready) / 4.0) * 0.7 + has_action * 0.3)
    actionability = min(1.0, has_how * 0.5 + min(1.0, len(ready) / 3.0) * 0.5)
    result_probability = min(1.0, has_result * 0.6 + actionability * 0.4)
    return {
        "specificity": round(specificity, 2),
        "actionability": round(actionability, 2),
        "result_probability": round(result_probability, 2),
    }


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_action_instance_blob(task, project=None, all_tasks: list[Any] | None = None) -> dict[str, Any] | None:
    base = task.business_action_json if isinstance(task.business_action_json, dict) else {}
    pack = base.get("execution_pack") if isinstance(base.get("execution_pack"), dict) else None
    if not pack:
        p = ensure_execution_pack_for_task(task, project, all_tasks=all_tasks)
        if not p:
            return None
        pack = p.model_dump()

    out = dict(base)
    out["execution_pack"] = pack

    action = out.get("action_instance") if isinstance(out.get("action_instance"), dict) else None
    if not action:
        action = {
            "action_id": f"act-{task.id}-{int(time.time())}",
            "task_id": task.id,
            "project_id": task.project_id,
            "action_type": pack.get("pack_type") or "generic_pack",
            "status": "pending",
            "created_at": _now_iso(),
            "started_at": "",
            "completed_at": "",
            "result_summary": "",
            "impact_score": "",
            "owner_feedback": "",
        }
    else:
        # Timestamp integrity: legacy action_instance может не иметь created_at.
        action.setdefault("created_at", _now_iso())
        action.setdefault("started_at", "")
        action.setdefault("completed_at", "")
    out["action_instance"] = action

    if not isinstance(out.get("result_snapshots"), list):
        out["result_snapshots"] = []

    if not isinstance(out.get("execution_metrics"), dict):
        out["execution_metrics"] = {
            "actions_started": 0,
            "actions_completed": 0,
            "useful_actions": 0,
            "useless_actions": 0,
        }

    out["execution_scoring"] = execution_scoring(pack)
    out["pack_learning"] = pack_learning_quality(str(pack.get("pack_type") or "generic_pack"), all_tasks)
    return out


def apply_action_feedback(
    blob: dict[str, Any],
    *,
    status: ActionStatus,
    owner_feedback: str = "",
    result_summary: str = "",
    result_type: str = "",
    result_value: str = "",
    notes: str = "",
) -> dict[str, Any]:
    out = dict(blob)
    action = out.get("action_instance") if isinstance(out.get("action_instance"), dict) else {}
    prev_status = str(action.get("status") or "pending")
    action.setdefault("created_at", _now_iso())
    action.setdefault("started_at", "")
    action.setdefault("completed_at", "")

    action["status"] = status
    if status == "in_progress" and not action.get("started_at"):
        action["started_at"] = _now_iso()
    if status in {"done", "skipped"}:
        action["completed_at"] = _now_iso()

    if owner_feedback:
        action["owner_feedback"] = owner_feedback[:2000]
    if result_summary:
        action["result_summary"] = result_summary[:2000]

    out["action_instance"] = action

    metrics = out.get("execution_metrics") if isinstance(out.get("execution_metrics"), dict) else {}
    metrics.setdefault("actions_started", 0)
    metrics.setdefault("actions_completed", 0)
    metrics.setdefault("useful_actions", 0)
    metrics.setdefault("useless_actions", 0)

    if status == "in_progress" and prev_status == "pending":
        metrics["actions_started"] += 1
    if status == "done" and prev_status != "done":
        metrics["actions_completed"] += 1

    fb = (owner_feedback or "").lower()
    if "не сработ" in fb or status == "skipped":
        metrics["useless_actions"] += 1
    elif status == "done":
        metrics["useful_actions"] += 1

    out["execution_metrics"] = metrics

    if status in {"done", "skipped"}:
        snaps = out.get("result_snapshots") if isinstance(out.get("result_snapshots"), list) else []
        snaps.append(
            {
                "project_id": action.get("project_id"),
                "action_id": action.get("action_id"),
                "result_type": result_type or _default_result_type(action.get("action_type")),
                "result_value": (result_value or result_summary or "")[:400],
                "notes": notes[:1000] if notes else owner_feedback[:1000],
            }
        )
        out["result_snapshots"] = snaps[-20:]

    return out


def _default_result_type(action_type: str | None) -> str:
    at = str(action_type or "").lower()
    if "content" in at:
        return "content"
    if "partner" in at or "outreach" in at:
        return "partner"
    if "offer" in at or "landing" in at:
        return "lead"
    return "sale"


def growth_insight_snapshot(all_tasks: list[Any] | None) -> dict[str, Any]:
    if not all_tasks:
        return {"top_packs": [], "weak_packs": [], "recommendations": []}
    return build_growth_insight(all_tasks)
