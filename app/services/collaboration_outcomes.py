# app/services/collaboration_outcomes.py — Phase 11.5: collaboration effectiveness (explainable, evidence-based)
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from app.services.collaboration_execution_store import get_execution
from app.services.collaboration_outcome_store import (
    get_outcome_by_execution,
    get_outcome_record,
    list_outcome_records,
    merge_outcome,
    outcome_id_for_execution,
    save_outcome_record,
)


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


def _capture_signal_bundle(project_key: Optional[str] = None) -> dict[str, Any]:
    """Снимок explainable-сигналов для сравнения до/после (без opaque score)."""
    from app.services.owner_insights import (
        get_awaiting_decisions_summary,
        get_rework_signal_summary,
        get_blockers_summary,
    )
    from app.services.owner_queries import get_system_status_summary
    from app.services.project_queries import list_projects

    awaiting = get_awaiting_decisions_summary(limit=50)
    rework = get_rework_signal_summary(limit=30)
    blockers = get_blockers_summary(limit=20)
    status = get_system_status_summary()
    bundle: dict[str, Any] = {
        "global_pending": int(awaiting.get("pending_count") or 0),
        "global_rework": int(rework.get("count") or 0),
        "global_blockers": int(blockers.get("blockers_count") or 0),
        "degraded": status.get("state") == "DEGRADED",
        "project_key": project_key,
        "project_pending": None,
        "project_rework": None,
        "project_long_running": None,
    }
    if project_key:
        for p in list_projects(limit=100).get("items", []):
            if str(p.get("project_key")) == str(project_key):
                bundle["project_pending"] = int(p.get("pending_count") or 0)
                bundle["project_rework"] = int(p.get("rework_signals") or 0)
                bundle["project_long_running"] = int(p.get("long_running") or 0)
                break
    return bundle


def _bundle_summary(b: dict[str, Any]) -> str:
    parts = [
        f"pending={b.get('global_pending')}",
        f"rework={b.get('global_rework')}",
        f"blockers={b.get('global_blockers')}",
        f"degraded={b.get('degraded')}",
    ]
    if b.get("project_key"):
        parts.append(
            f"project[{b.get('project_key')}] p={b.get('project_pending')} rw={b.get('project_rework')} lr={b.get('project_long_running')}"
        )
    return "; ".join(parts)


def _primary_metric(execution_type: str, subject_type: str, subject_key: str, bundle: dict[str, Any]) -> tuple[str, float]:
    """
    Возвращает (имя_метрики, числовое_значение для сравнения).
    runtime: degraded даёт +10 к «давлению», blockers добавляются.
    """
    st = (subject_type or "").lower()
    sk = str(subject_key or "")
    et = (execution_type or "").lower()

    if et in ("escalate_runtime_issue",):
        pressure = (10.0 if bundle.get("degraded") else 0.0) + float(bundle.get("global_blockers") or 0)
        return ("runtime_pressure", pressure)

    if et in ("request_owner_attention",):
        if st == "project" and sk:
            if bundle.get("project_pending") is None:
                return ("project_attention", float("nan"))
            v = (
                float(bundle.get("project_pending") or 0)
                + float(bundle.get("project_rework") or 0)
                + float(bundle.get("project_long_running") or 0)
            )
            return ("project_attention", v)
        return ("global_pending", float(bundle.get("global_pending") or 0))

    if et in ("request_review",):
        if st == "project" and sk and bundle.get("project_rework") is not None:
            return ("project_rework", float(bundle.get("project_rework") or 0))
        return ("global_rework", float(bundle.get("global_rework") or 0))

    if et in ("request_decision_resolution",):
        if st == "project" and sk:
            if bundle.get("project_pending") is None:
                return ("project_pending", float("nan"))
            return ("project_pending", float(bundle.get("project_pending") or 0))
        return ("global_pending", float(bundle.get("global_pending") or 0))

    if et in ("mark_handoff_followup",):
        return (
            "handoff_pressure",
            float(bundle.get("global_pending") or 0) + float(bundle.get("global_rework") or 0),
        )

    # acknowledge_collaboration_gap и прочее
    return (
        "collab_gap_pressure",
        float(bundle.get("global_pending") or 0) + float(bundle.get("global_rework") or 0),
    )


def record_collaboration_outcome_baseline_on_close(execution_id: str) -> Optional[dict[str, Any]]:
    """
    Вызывается при закрытии execution: фиксируем baseline сигналов в момент close.
    """
    ex = get_execution(execution_id)
    if not ex or (ex.get("execution_status") or "") != "closed":
        return None
    st = ex.get("subject_type") or "portfolio"
    sk = str(ex.get("subject_key") or "")
    project_key = sk if (st or "").lower() == "project" else None
    bundle = _capture_signal_bundle(project_key)
    oid = outcome_id_for_execution(execution_id)
    now = _now()
    existing = get_outcome_record(oid) or {}
    created_at = existing.get("created_at") or now
    rec = {
        "outcome_id": oid,
        "execution_id": execution_id,
        "suggestion_id": ex.get("suggestion_id"),
        "subject_type": st,
        "subject_key": sk,
        "roles_involved": _roles_from_execution(ex),
        "baseline_signal_bundle": bundle,
        "baseline_signal_state": _bundle_summary(bundle),
        "post_execution_signal_bundle": None,
        "post_execution_signal_state": None,
        "outcome_status": "pending_measurement",
        "effectiveness_label": "not_enough_signal",
        "outcome_reason": "Baseline зафиксирован при закрытии execution; evaluate позже",
        "followup_needed": True,
        "measured_at": now,
        "window_days": None,
        "baseline_captured_at": now,
        "execution_type": ex.get("execution_type"),
        "created_at": created_at,
    }
    save_outcome_record({**existing, **rec})
    return get_outcome_record(oid)


def _roles_from_execution(ex: dict[str, Any]) -> List[str]:
    roles = []
    for k in ("source_role", "target_role"):
        v = ex.get(k)
        if v and v not in roles:
            roles.append(str(v))
    snap = ex.get("suggestion_snapshot") or {}
    ri = snap.get("roles_involved")
    if isinstance(ri, list):
        for r in ri:
            if r and r not in roles:
                roles.append(str(r))
    return roles or ["owner"]


def evaluate_collaboration_execution_outcome(
    execution_id: str,
    window_days: int = 7,
) -> Optional[dict[str, Any]]:
    """
    Сравнение baseline (на момент close) с текущим снимком сигналов.
    """
    ex = get_execution(execution_id)
    if not ex:
        return None
    status_ex = (ex.get("execution_status") or "").lower()
    if status_ex == "cancelled":
        oid = outcome_id_for_execution(execution_id)
        return merge_outcome(oid, {
            "outcome_id": oid,
            "execution_id": execution_id,
            "outcome_status": "insufficient_data",
            "effectiveness_label": "not_enough_signal",
            "outcome_reason": "Execution отменён — outcome не оценивается",
            "followup_needed": False,
            "window_days": window_days,
            "measured_at": _now(),
        })
    if status_ex != "closed":
        oid = outcome_id_for_execution(execution_id)
        return merge_outcome(oid, {
            "outcome_id": oid,
            "execution_id": execution_id,
            "outcome_status": "insufficient_data",
            "effectiveness_label": "not_enough_signal",
            "outcome_reason": "Execution ещё не закрыт — сравнение baseline/post отложено",
            "followup_needed": True,
            "window_days": window_days,
            "measured_at": _now(),
        })

    st = ex.get("subject_type") or "portfolio"
    sk = str(ex.get("subject_key") or "")
    project_key = sk if (st or "").lower() == "project" else None
    et = ex.get("execution_type") or "acknowledge_collaboration_gap"

    oid = outcome_id_for_execution(execution_id)
    existing = get_outcome_record(oid)
    post_bundle = _capture_signal_bundle(project_key)
    post_summary = _bundle_summary(post_bundle)
    now = _now()

    if not existing or existing.get("baseline_signal_bundle") is None:
        merge_outcome(oid, {
            "outcome_id": oid,
            "execution_id": execution_id,
            "suggestion_id": ex.get("suggestion_id"),
            "subject_type": st,
            "subject_key": sk,
            "roles_involved": _roles_from_execution(ex),
            "post_execution_signal_bundle": post_bundle,
            "post_execution_signal_state": post_summary,
            "outcome_status": "insufficient_data",
            "effectiveness_label": "not_enough_signal",
            "outcome_reason": "Нет baseline (закрытие до Phase 11.5 или сбой записи); нельзя сравнить",
            "followup_needed": True,
            "window_days": window_days,
            "measured_at": now,
            "execution_type": et,
        })
        _audit(
            "collaboration_outcome_evaluated",
            execution_id=execution_id,
            outcome_id=oid,
            outcome_status="insufficient_data",
            effectiveness_label="not_enough_signal",
        )
        return get_outcome_record(oid)

    base_bundle = existing.get("baseline_signal_bundle") or {}
    name_b, val_b = _primary_metric(et, st, sk, base_bundle)
    name_a, val_a = _primary_metric(et, st, sk, post_bundle)

    if (isinstance(val_b, float) and math.isnan(val_b)) or (isinstance(val_a, float) and math.isnan(val_a)):
        ostatus = "insufficient_data"
        reason = f"Недостаточно данных по метрике «{name_b}» (проект не найден в сводке)"
        followup = True
        eff = "not_enough_signal"
    else:
        eps = 1e-6
        if val_a < val_b - eps:
            ostatus = "improved"
            reason = f"Метрика «{name_b}» снизилась: {val_b} → {val_a} (окно оценки {window_days}д)"
            followup = False
            eff = "effective"
        elif val_a > val_b + eps:
            ostatus = "worse"
            reason = f"Метрика «{name_b}» выросла: {val_b} → {val_a}"
            followup = True
            eff = "ineffective"
        else:
            ostatus = "unchanged"
            reason = f"Метрика «{name_b}» без существенного изменения ({val_b} → {val_a})"
            followup = True
            eff = "partially_effective"

        # Короткое окно: меньше уверенности
        if window_days < 3 and ostatus == "unchanged":
            ostatus = "insufficient_data"
            reason += "; короткое окно — вывод ослаблен"
            eff = "not_enough_signal"
            followup = True

    merged = merge_outcome(oid, {
        "outcome_id": oid,
        "execution_id": execution_id,
        "suggestion_id": ex.get("suggestion_id"),
        "subject_type": st,
        "subject_key": sk,
        "roles_involved": _roles_from_execution(ex),
        "post_execution_signal_bundle": post_bundle,
        "post_execution_signal_state": post_summary,
        "primary_metric": name_b,
        "baseline_metric_value": val_b,
        "post_metric_value": val_a,
        "outcome_status": ostatus,
        "effectiveness_label": eff if ostatus != "insufficient_data" else "not_enough_signal",
        "outcome_reason": reason,
        "followup_needed": followup,
        "window_days": window_days,
        "measured_at": now,
        "execution_type": et,
    })

    if ostatus == "insufficient_data" and followup:
        _audit(
            "collaboration_outcome_followup_needed",
            execution_id=execution_id,
            outcome_id=oid,
            reason=reason,
        )
    elif followup and ostatus in ("unchanged", "worse"):
        _audit(
            "collaboration_outcome_followup_needed",
            execution_id=execution_id,
            outcome_id=oid,
            outcome_status=ostatus,
        )
    if eff == "effective" or ostatus == "improved":
        _audit(
            "collaboration_execution_effective",
            execution_id=execution_id,
            outcome_id=oid,
            primary_metric=name_b,
        )
    if eff == "ineffective" or ostatus == "worse":
        _audit(
            "collaboration_execution_ineffective",
            execution_id=execution_id,
            outcome_id=oid,
            outcome_status=ostatus,
        )
    _audit(
        "collaboration_outcome_evaluated",
        execution_id=execution_id,
        outcome_id=oid,
        outcome_status=ostatus,
        effectiveness_label=merged.get("effectiveness_label"),
    )
    return merged


def get_collaboration_execution_outcome(execution_id: str) -> Optional[dict[str, Any]]:
    return get_outcome_by_execution(execution_id)


def _parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def list_collaboration_outcomes(window_days: int = 30, limit: int = 100) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    items: List[dict[str, Any]] = []
    for rec in list_outcome_records(limit=500):
        mt = _parse_ts(rec.get("measured_at")) or _parse_ts(rec.get("baseline_captured_at"))
        if mt and mt >= cutoff:
            items.append(rec)
    items = items[:limit]
    return {"items": items, "count": len(items), "window_days": window_days}


def get_collaboration_effectiveness_summary(window_days: int = 30) -> dict[str, Any]:
    from collections import defaultdict

    raw = list_collaboration_outcomes(window_days=window_days, limit=300).get("items", [])
    effective = sum(1 for i in raw if i.get("effectiveness_label") == "effective")
    ineffective = sum(1 for i in raw if i.get("effectiveness_label") == "ineffective")
    partial = sum(1 for i in raw if i.get("effectiveness_label") == "partially_effective")
    ne = sum(1 for i in raw if i.get("effectiveness_label") == "not_enough_signal")
    followup = sum(1 for i in raw if i.get("followup_needed"))
    explainable = True

    by_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for i in raw:
        et = i.get("execution_type") or "unknown"
        lab = i.get("effectiveness_label") or "unknown"
        by_type[et][lab] += 1
    effectiveness_by_execution_type = {k: dict(v) for k, v in by_type.items()}

    pair_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for i in raw:
        roles = i.get("roles_involved") or []
        if len(roles) >= 2:
            a, b = sorted([str(roles[0]), str(roles[1])])
            key = f"{a}+{b}"
        elif len(roles) == 1:
            key = str(roles[0])
        else:
            key = "unknown"
        lab = i.get("effectiveness_label") or "unknown"
        pair_counts[key][lab] += 1
    effectiveness_by_role_pair = {k: dict(v) for k, v in pair_counts.items()}

    by_project: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for i in raw:
        if (i.get("subject_type") or "").lower() != "project":
            continue
        pk = str(i.get("subject_key") or "")
        if not pk:
            continue
        lab = i.get("effectiveness_label") or "unknown"
        by_project[pk][lab] += 1
    effectiveness_by_project = {k: dict(v) for k, v in by_project.items()}

    return {
        "window_days": window_days,
        "effective_executions_count": effective,
        "ineffective_executions_count": ineffective,
        "partially_effective_count": partial,
        "not_enough_signal_count": ne,
        "followup_needed_count": followup,
        "total_outcomes_in_window": len(raw),
        "explainable": explainable,
        "evidence_source": "collaboration_outcomes.json + owner_insights snapshots",
        "effectiveness_by_execution_type": effectiveness_by_execution_type,
        "effectiveness_by_role_pair": effectiveness_by_role_pair,
        "effectiveness_by_project": effectiveness_by_project,
    }


def get_collaboration_effectiveness_hotspots(window_days: int = 30, limit: int = 12) -> dict[str, Any]:
    """Где ineffective/unchanged pattern чаще (по execution_type + subject)."""
    raw = list_collaboration_outcomes(window_days=window_days, limit=300).get("items", [])
    buckets: dict[str, dict[str, Any]] = {}
    for i in raw:
        if i.get("effectiveness_label") not in ("ineffective", "partially_effective"):
            continue
        et = i.get("execution_type") or "unknown"
        sk = f"{i.get('subject_type')}:{i.get('subject_key')}"
        key = f"{et}|{sk}"
        buckets.setdefault(key, {"execution_type": et, "subject_type": i.get("subject_type"), "subject_key": i.get("subject_key"), "count": 0, "sample_reasons": []})
        buckets[key]["count"] += 1
        r = i.get("outcome_reason")
        if r and len(buckets[key]["sample_reasons"]) < 2:
            buckets[key]["sample_reasons"].append(str(r)[:120])
    sorted_hot = sorted(buckets.values(), key=lambda x: x["count"], reverse=True)[:limit]
    return {
        "window_days": window_days,
        "items": sorted_hot,
        "evidence_source": "aggregated collaboration outcomes (ineffective + partially_effective)",
    }


def get_followup_needed_executions(window_days: int = 30, limit: int = 50) -> dict[str, Any]:
    raw = list_collaboration_outcomes(window_days=window_days, limit=300).get("items", [])
    need = [i for i in raw if i.get("followup_needed")]
    return {"items": need[:limit], "count": len(need[:limit]), "window_days": window_days}


def get_execution_effectiveness_summary(execution_id: str) -> dict[str, Any]:
    o = get_outcome_by_execution(execution_id)
    if not o:
        return {"execution_id": execution_id, "has_outcome": False}
    return {
        "execution_id": execution_id,
        "has_outcome": True,
        "outcome_status": o.get("outcome_status"),
        "effectiveness_label": o.get("effectiveness_label"),
        "followup_needed": o.get("followup_needed"),
        "outcome_reason": o.get("outcome_reason"),
        "measured_at": o.get("measured_at"),
    }
