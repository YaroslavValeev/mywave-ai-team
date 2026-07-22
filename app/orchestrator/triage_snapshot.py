"""Канонический triage: снимок в JSON + согласование с колонками Task для court/summary."""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_routing
from app.orchestrator.exploration import detect_exploration_intent
from app.orchestrator.revenue_intent import detect_revenue_intent
from app.orchestrator.triage import REVENUE_OVERRIDE_DOMAIN, REVENUE_OVERRIDE_TASK_TYPE
from app.storage.repositories import TaskRepository

logger = logging.getLogger(__name__)


def _routing_revenue_cfg() -> dict[str, Any]:
    routing = get_routing()
    domains_cfg = routing.get("domains", {})
    tt_cfg = (domains_cfg.get(REVENUE_OVERRIDE_DOMAIN) or {}).get("task_types", {})
    return tt_cfg.get(REVENUE_OVERRIDE_TASK_TYPE, {}) or {}


def _revenue_locked(meta: dict[str, Any], triage_dict: dict[str, Any], owner_text: str) -> bool:
    if bool(triage_dict.get("revenue_intent_override")):
        return True
    if bool(meta.get("revenue_intent_override")):
        return True
    return detect_revenue_intent(owner_text or "")


def _apply_revenue_lock(out: dict[str, Any]) -> None:
    cfg = _routing_revenue_cfg()
    out["domain"] = REVENUE_OVERRIDE_DOMAIN
    out["task_type"] = REVENUE_OVERRIDE_TASK_TYPE
    out["revenue_intent_override"] = True
    out["plan_or_execute"] = "EXECUTE"
    out["execute_gate"] = cfg.get("execute_gate", out.get("execute_gate") or "OWNER_APPROVAL_IF_PROD")
    out["criticality"] = cfg.get("criticality", out.get("criticality") or "HIGH")


def persist_triage_snapshot(repo: TaskRepository, task_id: int, triage_result: dict[str, Any]) -> None:
    """Сохранить полный triage в business_action_json.triage_meta (источник истины для court)."""
    task = repo.get_task(task_id)
    if not task:
        return
    ba = dict(task.business_action_json or {})
    ba["triage_meta"] = {
        "revenue_intent_override": bool(triage_result.get("revenue_intent_override")),
        "exploration_mode": bool(triage_result.get("exploration_mode")),
        "domain": triage_result.get("domain"),
        "task_type": triage_result.get("task_type"),
        "criticality": triage_result.get("criticality"),
        "plan_or_execute": triage_result.get("plan_or_execute"),
        "execute_gate": triage_result.get("execute_gate"),
    }
    repo.update_task(task_id, business_action_json=ba)


def resync_triage_dict_from_store(repo: TaskRepository, task_id: int, triage_result: dict[str, Any]) -> dict[str, Any]:
    """Подтянуть triage_meta и колонки Task; revenue-lock важнее устаревшего meta.domain."""
    out = dict(triage_result)
    task = repo.get_task(task_id)
    if not task:
        return out
    ba = task.business_action_json if isinstance(task.business_action_json, dict) else {}
    meta = ba.get("triage_meta") if isinstance(ba.get("triage_meta"), dict) else {}
    raw = (task.owner_text or "").strip()

    if _revenue_locked(meta, out, raw):
        for key in ("criticality", "plan_or_execute", "execute_gate"):
            if meta.get(key) is not None:
                out[key] = meta[key]
        _apply_revenue_lock(out)
        return out

    # exploration_mode не мержим вслепую из meta: False в JSON перезаписывал бы свежий True из triage.
    for key in ("domain", "task_type", "criticality", "plan_or_execute", "execute_gate", "revenue_intent_override"):
        if key in meta and meta[key] is not None:
            out[key] = meta[key]
    if not out.get("domain") and getattr(task, "domain", None):
        out["domain"] = task.domain
    if not out.get("task_type") and getattr(task, "task_type", None):
        out["task_type"] = task.task_type
    if not out.get("criticality") and getattr(task, "criticality", None):
        out["criticality"] = task.criticality
    if not out.get("plan_or_execute") and getattr(task, "plan_or_execute", None):
        out["plan_or_execute"] = task.plan_or_execute
    out["exploration_mode"] = bool(triage_result.get("exploration_mode")) or detect_exploration_intent(raw)
    return out


def canonical_triage_for_court(task: Any, triage_result: dict[str, Any]) -> dict[str, Any]:
    """Court и Telegram summary: revenue-lock не даёт устаревшему meta.domain затереть BUSINESS."""
    out = dict(triage_result or {})
    ba = task.business_action_json if isinstance(getattr(task, "business_action_json", None), dict) else {}
    meta = ba.get("triage_meta") if isinstance(ba.get("triage_meta"), dict) else {}
    raw = (getattr(task, "owner_text", None) or "").strip()

    if _revenue_locked(meta, out, raw):
        for key in ("criticality", "plan_or_execute", "execute_gate"):
            if meta.get(key) is not None and out.get(key) is None:
                out[key] = meta[key]
        _apply_revenue_lock(out)
        logger.info(
            "COURT INPUT (revenue-lock) domain=%s task_type=%s override=%s task.domain_col=%s",
            out.get("domain"),
            out.get("task_type"),
            out.get("revenue_intent_override"),
            getattr(task, "domain", None),
        )
        return out

    for key in ("domain", "task_type", "criticality", "plan_or_execute", "execute_gate", "revenue_intent_override"):
        if key in meta and meta[key] is not None:
            out[key] = meta[key]
    if not out.get("domain") and getattr(task, "domain", None):
        out["domain"] = task.domain
    if not out.get("task_type") and getattr(task, "task_type", None):
        out["task_type"] = task.task_type
    if not out.get("criticality") and getattr(task, "criticality", None):
        out["criticality"] = task.criticality
    if not out.get("plan_or_execute") and getattr(task, "plan_or_execute", None):
        out["plan_or_execute"] = task.plan_or_execute
    out["exploration_mode"] = bool((triage_result or {}).get("exploration_mode")) or detect_exploration_intent(raw)
    logger.info(
        "COURT INPUT domain=%s task_type=%s override=%s task.domain_col=%s",
        out.get("domain"),
        out.get("task_type"),
        out.get("revenue_intent_override"),
        getattr(task, "domain", None),
    )
    return out
