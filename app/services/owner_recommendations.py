# app/services/owner_recommendations.py — Phase 9.3: strategic digests and explainable recommendations
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Any

from sqlalchemy import text

from app.services.owner_insights import (
    get_awaiting_decisions_summary,
    get_blockers_summary,
    get_long_running_summary,
    get_rework_signal_summary,
    get_degraded_signal_summary,
    get_weekly_digest,
    get_project_activity_summary,
)
from app.services.owner_queries import get_system_status_summary
from app.storage.repositories import get_session_factory, TaskRepository
from app.storage.models import TaskStatus


def _project_key(task: Any) -> str:
    k = (getattr(task, "domain", None) or getattr(task, "task_type", None) or "general")
    return (k or "general").strip() or "general"


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_next_actions(limit: int = 5) -> dict[str, Any]:
    """Приоритизированные следующие шаги для owner (rule-based, explainable)."""
    awaiting = get_awaiting_decisions_summary(limit=limit)
    degraded = get_degraded_signal_summary(limit=1)
    blockers = get_blockers_summary(limit=limit)
    rework = get_rework_signal_summary(limit=limit)
    long_running = get_long_running_summary(limit=limit)
    actions = []
    seen_task_ids = set()

    def add(action_type: str, task_id: int | None, reason: str, priority: str, suggested: str, if_deferred: str | None = None, rationale_headline: str | None = None, evidence_summary: list | None = None, suggested_safe_action: str | None = None):
        if task_id and task_id in seen_task_ids:
            return
        if task_id:
            seen_task_ids.add(task_id)
        item = {
            "action_type": action_type,
            "task_id": task_id,
            "reason": reason,
            "priority": priority,
            "suggested_action": suggested,
            "if_deferred": if_deferred,
        }
        if rationale_headline is not None:
            item["rationale_headline"] = rationale_headline
        if evidence_summary is not None:
            item["evidence_summary"] = evidence_summary
        if suggested_safe_action is not None:
            item["suggested_safe_action"] = suggested_safe_action
        actions.append(item)

    for t in awaiting["items"][:limit]:
        add("approval", t.id, "Pending owner decision", "high", "Разобрать approve/rework/clarify", "Решения будут копиться")
    if degraded["current_state"] == "DEGRADED":
        add("degraded", None, "Runtime degraded", "high", "Проверить Molt / boundary / логи", "Риск срыва выполнения")
    for i in blockers.get("items", [])[:limit]:
        t = i.get("task")
        if not t or t.id in seen_task_ids:
            continue
        add("blocker", t.id, i.get("kind", "blocker"), "medium", "Снять блокер или пересмотреть приоритет", "Задача останется зависшей")
    for t in rework.get("items", [])[:limit]:
        if t.id in seen_task_ids:
            continue
        add("rework", t.id, f"Repeated rework (cycles={getattr(t, 'rework_cycles', 0)})", "medium", "Owner review / уточнение постановки", "Риск повторного rework")
    for i in long_running.get("items", [])[:limit]:
        t = i.get("task")
        if not t or t.id in seen_task_ids:
            continue
        add("long_running", t.id, i.get("reason", "stale"), "medium", "Пересмотреть приоритеты или завершить/отложить", "Будет копиться backlog")
    try:
        att = get_pending_refinement_attention()
        if (att.get("pending_count") or 0) >= 1:
            add("refinement_review", None, f"{att.get('pending_count')} refinement proposals на ревью", "low", "Просмотреть /owner/refinement/proposals или /refinement_proposals", "Backlog рефайнмента будет копиться")
        if (att.get("safe_patch_candidates_count") or 0) >= 1:
            add("refinement_patch_apply", None, f"{att.get('safe_patch_candidates_count')} accepted proposals готовы к safe apply", "low", "Просмотреть /owner/refinement/proposals?status=accepted → Patch или /dry_run_patch, /apply_patch", "Изменения в реестр не применятся")
        if (att.get("failed_patch_validation_count") or 0) >= 1:
            add("refinement_patch_validation", None, f"{att.get('failed_patch_validation_count')} proposals с ошибкой валидации патча", "low", "Проверить /owner/refinement/proposal/<id>/patch → Validate", "Требуется ручное исправление")
    except Exception:
        pass
    try:
        from app.services.agent_tuning_workflows import get_specialization_tuning_summary
        tun = get_specialization_tuning_summary(window_days=30)
        if (tun.get("pending_count") or 0) >= 1:
            add("tuning_review", None, f"{tun.get('pending_count')} tuning candidates на ревью", "low", "Просмотреть /owner/tuning или /tuning_candidates", "Execution lane tuning будет копиться")
    except Exception:
        pass
    try:
        from app.services.tuning_patch_integration import list_patchable_tuning_candidates
        from app.services.tuning_outcomes import get_tuning_outcome_summary, list_tuning_outcomes

        pl = list_patchable_tuning_candidates(window_days=30, limit=50)
        if (pl.get("count") or 0) >= 1:
            add("patchable_tuning_candidate_signal", None, f"{pl.get('count')} tuning candidate(s) patchable (safe path)", "low", "/owner/tuning или /patchable_tuning", "Semi-automated tuning не используется")

        osum = get_tuning_outcome_summary(window_days=30)
        if (osum.get("pending_measurement_count") or 0) >= 1:
            add("tuning_outcome_needs_followup", None, f"{osum.get('pending_measurement_count')} tuning outcome(s) ждут evaluate", "low", "/owner/tuning/outcomes — POST evaluate-outcome", "Нельзя подтвердить эффект патча")
        if (osum.get("improved_count") or 0) >= 1:
            add("successful_tuning_improvement_signal", None, f"{osum.get('improved_count')} verified tuning improvement(s)", "low", "/tuning_outcomes", None)
        if (osum.get("worse_count") or 0) >= 1:
            outs = list_tuning_outcomes(window_days=30, limit=20).get("items", [])
            if any(o.get("outcome_status") == "worse" for o in outs):
                add("failed_tuning_patch_signal", None, "Есть tuning outcome: worse после patch", "medium", "/owner/tuning/outcomes — ручной review", "Риск деградации execution lane")
    except Exception:
        pass
    try:
        from app.services.collaboration_execution import get_pending_collaboration_executions

        pe = get_pending_collaboration_executions(window_days=14, limit=50)
        n = pe.get("summary", {}).get("pending_count") or len(pe.get("items", []))
        if n >= 1:
            add(
                "pending_collaboration_execution_attention",
                None,
                f"{n} открыт(ых) collaboration execution(s)",
                "low",
                "/owner/collaboration/executions или /collaboration_executions",
                "Handoff follow-up не отслеживается",
            )
    except Exception:
        pass
    try:
        from app.services.collaboration_outcomes import (
            get_followup_needed_executions,
            get_collaboration_effectiveness_summary,
            get_collaboration_effectiveness_hotspots,
        )

        fu = get_followup_needed_executions(window_days=30, limit=40)
        if (fu.get("count") or 0) >= 2:
            add(
                "collaboration_execution_followup_signal",
                None,
                f"{fu.get('count')} collaboration outcome(s) с follow-up (сигнал не снят или мало данных)",
                "low",
                "/owner/collaboration/outcomes или /collaboration_followup",
                "Повторная координация может понадобиться",
            )
        osum = get_collaboration_effectiveness_summary(window_days=30)
        if (osum.get("ineffective_executions_count") or 0) >= 2:
            add(
                "ineffective_collaboration_pattern_signal",
                None,
                f"{osum.get('ineffective_executions_count')} ineffective collaboration outcome(s) в окне",
                "medium",
                "/owner/collaboration/outcomes — пересмотреть паттерн",
                "Интервенции не снизили выбранную метрику",
            )
        if (osum.get("effective_executions_count") or 0) >= 3:
            add(
                "effective_collaboration_pattern_signal",
                None,
                f"{osum.get('effective_executions_count')} effective collaboration outcome(s) — паттерн работает",
                "low",
                "/collaboration_outcomes",
                None,
            )
        hot = get_collaboration_effectiveness_hotspots(window_days=30, limit=10)
        for h in hot.get("items", []):
            if (h.get("count") or 0) >= 2 and (h.get("subject_type") or "").lower() == "project" and h.get("subject_key"):
                add(
                    "project_collaboration_needs_revisit",
                    None,
                    f"Проект {h.get('subject_key')}: повторяющиеся слабые collaboration outcomes ({h.get('execution_type')})",
                    "medium",
                    f"/owner/project/{h.get('subject_key')} и /owner/collaboration/outcomes",
                    "Стоит пересмотреть координацию по проекту",
                )
                break
    except Exception:
        pass
    try:
        from app.services.cross_layer_effectiveness import get_layer_alignment_signals

        align = get_layer_alignment_signals(window_days=30)
        conflict = [a for a in align if a.get("conflict_type") == "collaboration_improved_tuning_worse"]
        if conflict:
            add(
                "cross_layer_alignment_conflict_signal",
                None,
                "Collaboration улучшил, tuning — ухудшил (рассогласование слоёв)",
                "medium",
                "/owner/effectiveness — cross-layer synthesis",
                "Стоит пересмотреть порядок интервенций",
            )
    except Exception:
        pass
    try:
        from app.services.project_domain_lifecycle import get_project_domain_drift_signals, get_project_domain_instability_signals
        drift = get_project_domain_drift_signals(window_days=30, limit=5)
        if drift:
            add("project_domain_drift_signal", None, f"{len(drift)} проект(ов) со сменой доминанты домена", "low", "Просмотреть /owner/portfolio (Domain lifecycle) или /domain_lifecycle", "Дрифт доменного профиля может требовать уточнения")
        instab = get_project_domain_instability_signals(window_days=30, limit=5)
        if instab:
            add("project_domain_instability_signal", None, f"{len(instab)} проект(ов) с нестабильным/override-heavy доменом", "low", "Просмотреть /owner/portfolio или /project_lifecycle <key>", "Рекомендуется проверить доменный профиль")
    except Exception:
        pass
    try:
        from app.services.project_domain_evolution_refinement import (
            list_project_domain_attention_items,
            get_drift_requiring_intervention,
            get_diversification_requiring_review,
        )
        attn = list_project_domain_attention_items(window_days=30, limit=10)
        if attn:
            add("project_domain_evolution_attention", None, f"{len(attn)} проект(ов) требует внимания по domain evolution", "medium", "/owner/portfolio — Domain evolution или /domain_evolution", "Рекомендуется refinement/tuning")
        drift_iv = get_drift_requiring_intervention(window_days=30, limit=5)
        if drift_iv:
            add("project_domain_drift_requiring_intervention", None, f"{len(drift_iv)} проект(ов): harmful drift — intervention", "medium", "/owner/portfolio · domain evolution", "Domain drift требует refinement")
        div_rev = get_diversification_requiring_review(window_days=30, limit=5)
        if div_rev:
            add("project_domain_diversification_requiring_review", None, f"{len(div_rev)} проект(ов): unstable mix — review", "low", "/owner/portfolio · domain evolution", "Diversification требует проверки")
    except Exception:
        pass
    try:
        from app.services.collaboration_flows import get_collaboration_hotspots
        hotspots = get_collaboration_hotspots(window_days=7, limit=10)
        seen_types = set()
        for h in hotspots:
            ht = h.get("hotspot_type", "")
            if ht in seen_types:
                continue
            seen_types.add(ht)
            if ht == "approval_bottleneck":
                add("approval_bottleneck_signal", None, h.get("reason", "Approval bottleneck"), "high", h.get("recommended_collaboration_action", "Разобрать approvals"), "Backlog будет расти", rationale_headline=h.get("reason", "Approval bottleneck"), evidence_summary=[h.get("recommended_collaboration_action", "")[:80]] if h.get("recommended_collaboration_action") else None, suggested_safe_action="open_decision_queue")
            elif ht == "review_execution_loop":
                add("review_execution_loop_signal", None, h.get("reason", "Review–execution loop"), "medium", h.get("recommended_collaboration_action", "Координировать owner–executor"), "Риск повторного rework", rationale_headline=h.get("reason", "Review–execution loop"), evidence_summary=[h.get("recommended_collaboration_action", "")[:80]] if h.get("recommended_collaboration_action") else None)
            elif ht == "owner_attention_gap":
                add("owner_attention_gap_signal", None, h.get("reason", "Owner attention gap"), "medium", h.get("recommended_collaboration_action", "Выделить внимание owner"), "Проект может застрять", rationale_headline=h.get("reason", "Owner attention gap"), evidence_summary=[h.get("recommended_collaboration_action", "")[:80]] if h.get("recommended_collaboration_action") else None)
            elif ht == "runtime_escalation_gap":
                add("runtime_escalation_signal", None, h.get("reason", "Runtime escalation gap"), "high", h.get("recommended_collaboration_action", "Operator → owner escalation"), "Риск срыва выполнения", rationale_headline=h.get("reason", "Runtime escalation gap"), evidence_summary=[h.get("recommended_collaboration_action", "")[:80]] if h.get("recommended_collaboration_action") else None, suggested_safe_action="recheck_molt_health")
            elif ht == "domain_handoff_mismatch":
                add("collaboration_hotspot_signal", None, h.get("reason", "Domain handoff mismatch"), "low", h.get("recommended_collaboration_action", "Проверить доменный профиль"), "Рекомендуется координация", rationale_headline=h.get("reason", "Domain handoff mismatch"), evidence_summary=[h.get("recommended_collaboration_action", "")[:80]] if h.get("recommended_collaboration_action") else None)
    except Exception:
        pass
    return {"items": actions[:limit], "count": len(actions[:limit])}


def get_decision_queue(limit: int = 10) -> dict[str, Any]:
    """Очередь решений: что требует решения первым, почему, что будет при игнорировании."""
    awaiting = get_awaiting_decisions_summary(limit=limit * 2)
    long_running = get_long_running_summary(limit=limit)
    degraded = get_degraded_signal_summary(limit=1)
    rework = get_rework_signal_summary(limit=limit)
    queue = []
    seen = set()

    for t in awaiting["items"]:
        if t.id in seen:
            continue
        seen.add(t.id)
        queue.append({
            "task_id": t.id,
            "reason": "Pending approval / decision",
            "priority": "high",
            "suggested_next_action": "Принять решение: approve / rework / clarify",
            "if_ignored": "Решения будут копиться, поток замедлится",
        })
    for i in long_running["items"]:
        t = i.get("task")
        if not t or t.id in seen:
            continue
        seen.add(t.id)
        queue.append({
            "task_id": t.id,
            "reason": i.get("reason", "Long-running / stale"),
            "priority": "medium",
            "suggested_next_action": "Решить или отложить задачу",
            "if_ignored": "Задача останется в подвешенном состоянии",
        })
    if degraded["current_state"] == "DEGRADED":
        queue.append({
            "task_id": None,
            "reason": "System degraded",
            "priority": "high",
            "suggested_next_action": "Проверить runtime / логи",
            "if_ignored": "Риск срыва выполнения задач",
        })
    for t in rework["items"]:
        if t.id in seen:
            continue
        seen.add(t.id)
        queue.append({
            "task_id": t.id,
            "reason": f"Repeated rework (cycles={getattr(t, 'rework_cycles', 0)})",
            "priority": "medium",
            "suggested_next_action": "Уточнить постановку или принять результат",
            "if_ignored": "Риск повторного rework",
        })
    return {"items": queue[:limit], "count": len(queue[:limit])}


def get_project_health_summary(limit: int = 10) -> dict[str, Any]:
    """По группам (project baseline): healthy / attention_needed / critical."""
    now = datetime.now(timezone.utc)
    wait_threshold = now - timedelta(hours=24)
    progress_threshold = now - timedelta(hours=6)
    status = get_system_status_summary()
    degraded_now = status.get("state") == "DEGRADED"
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    by_project = defaultdict(lambda: {"pending": 0, "active": 0, "rework_signals": 0, "long_running": 0})
    for t in tasks:
        key = _project_key(t)
        if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value):
            by_project[key]["pending"] += 1
        if t.status not in (TaskStatus.DONE.value, TaskStatus.ARCHIVED.value):
            by_project[key]["active"] += 1
        if (getattr(t, "rework_cycles", 0) or 0) >= 2 or t.status == TaskStatus.REWORK.value:
            by_project[key]["rework_signals"] += 1
        updated = _to_utc(t.updated_at) or _to_utc(t.created_at)
        if updated:
            if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value) and updated < wait_threshold:
                by_project[key]["long_running"] += 1
            elif t.status in (TaskStatus.IN_PIPELINE.value, TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value) and updated < progress_threshold:
                by_project[key]["long_running"] += 1
    result = []
    for project, counts in by_project.items():
        p, a, rw, lr = counts["pending"], counts["active"], counts["rework_signals"], counts["long_running"]
        if p >= 2 or (degraded_now and a > 0) or (rw >= 2 or lr >= 2):
            status_str = "critical"
            reason = "Порог блокеров/rework/degraded превышен"
        elif p >= 1 or rw >= 1 or lr >= 1:
            status_str = "attention_needed"
            reason = "Есть pending / rework / long-running"
        else:
            status_str = "healthy"
            reason = "Нет критичных сигналов"
        result.append({
            "project": project,
            "status": status_str,
            "reason": reason,
            "active_count": a,
            "pending_count": p,
            "rework_signals": rw,
            "long_running": lr,
        })
    result.sort(key=lambda x: (x["status"] == "critical", x["status"] == "attention_needed", -x["pending_count"]))
    return {"items": result[:limit], "count": len(result)}


def get_priority_signals(limit: int = 5) -> dict[str, Any]:
    """Сигналы приоритета: на что обратить внимание."""
    next_data = get_next_actions(limit=limit)
    signals = []
    for a in next_data["items"]:
        signals.append({
            "kind": a["action_type"],
            "reason": a["reason"],
            "priority": a["priority"],
            "suggested_action": a["suggested_action"],
        })
    return {"items": signals[:limit], "count": len(signals)}


def get_risk_signals(limit: int = 5) -> dict[str, Any]:
    """Риски с объяснением: почему важно, что делать."""
    degraded = get_degraded_signal_summary(limit=1)
    awaiting = get_awaiting_decisions_summary(limit=1)
    rework = get_rework_signal_summary(limit=1)
    long_running = get_long_running_summary(limit=1)
    risks = []
    if degraded["current_state"] == "DEGRADED" or (degraded.get("events_count_7d") or 0) > 0:
        risks.append({
            "risk_type": "degraded_frequency",
            "reason": "Runtime/ boundary нестабильны или были инциденты за 7 дней",
            "why_it_matters": "Риск срыва выполнения задач",
            "suggested_action": "Проверить Molt / логи / boundary",
        })
    if awaiting["pending_count"] >= 2:
        risks.append({
            "risk_type": "approvals_backlog",
            "reason": f"Pending approvals: {awaiting['pending_count']}",
            "why_it_matters": "Замедляет поток и блокирует завершение",
            "suggested_action": "Разобрать approvals",
        })
    if rework["count"] >= 2:
        risks.append({
            "risk_type": "rework_accumulation",
            "reason": f"Повторный rework по {rework['count']} задачам",
            "why_it_matters": "Качество постановки или исполнения требует внимания",
            "suggested_action": "Разбор тренда и приоритетов",
        })
    if long_running["count"] > 0:
        risks.append({
            "risk_type": "long_running_accumulation",
            "reason": f"Задачи без прогресса: {long_running['count']}",
            "why_it_matters": "Блокируют обзор и создают backlog",
            "suggested_action": "Решить или отложить задачи",
        })
    return {"items": risks[:limit], "count": len(risks)}


def get_strategic_weekly_digest() -> dict[str, Any]:
    """Стратегическая недельная сводка: риски, что сдвинулось, что застопорилось, приоритеты."""
    weekly = get_weekly_digest(limit=5)
    risks = get_risk_signals(limit=5)
    decision_queue = get_decision_queue(limit=5)
    next_actions = get_next_actions(limit=3)
    return {
        "window_days": 7,
        "completed_count": weekly.get("completed_count", 0),
        "pending_approvals_count": weekly.get("pending_approvals_count", 0),
        "blockers_count": weekly.get("blockers_count", 0),
        "rework_count": weekly.get("rework_count", 0),
        "degraded_events_count": weekly.get("degraded_events_count", 0),
        "key_risks": risks.get("items", []),
        "what_moved": weekly.get("top_completed", [])[:3],
        "what_stalled": weekly.get("top_blockers", [])[:3],
        "needs_decision": decision_queue.get("items", [])[:5],
        "next_week_priorities": next_actions.get("items", [])[:3],
        "owner_focus": weekly.get("owner_focus", ""),
    }


def get_monthly_digest_baseline() -> dict[str, Any]:
    """Baseline месячной сводки: последние 30 дней."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
        decisions_count = session.execute(
            text("SELECT COUNT(*) FROM decisions WHERE created_at >= :since"),
            {"since": since},
        ).scalar() or 0
        rework_count = session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE event_type = 'OWNER_REWORK' AND created_at >= :since"),
            {"since": since},
        ).scalar() or 0
        error_count = session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE (event_type LIKE '%error%' OR event_type LIKE '%degraded%' OR event_type LIKE '%rollback%') AND created_at >= :since"),
            {"since": since},
        ).scalar() or 0
    completed = [t for t in tasks if t.status == TaskStatus.DONE.value and _to_utc(t.updated_at) and _to_utc(t.updated_at) >= since]
    active = [t for t in tasks if t.status not in (TaskStatus.DONE.value, TaskStatus.ARCHIVED.value)]
    pending = [t for t in tasks if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    blockers = get_blockers_summary(limit=5)
    next_actions = get_next_actions(limit=3)
    return {
        "window_days": 30,
        "completed_count": len(completed),
        "active_count": len(active),
        "pending_approvals_count": len(pending),
        "rework_count": int(rework_count),
        "degraded_incidents_count": int(error_count),
        "top_blockers": blockers.get("items", [])[:5],
        "top_recommendations": next_actions.get("items", [])[:3],
    }


def get_domain_aware_signals(limit_tasks: int = 20, limit_signals: int = 5) -> dict[str, Any]:
    """
    Phase 10.0/10.1: domain-aware recommendation signals (explainable).
    Группирует активные/ожидающие задачи по effective expertise domain (с учётом override).
    """
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
    except ImportError:
        return {"items": [], "count": 0, "explainable": True}

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()

    active_statuses = {
        TaskStatus.NEW.value, TaskStatus.TRIAGED.value, TaskStatus.IN_PIPELINE.value,
        TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value,
        TaskStatus.WAIT_OWNER.value, TaskStatus.REWORK.value, TaskStatus.NEED_INFO.value,
        TaskStatus.APPROVED_WAIT_MERGE.value,
    }
    subset = [t for t in tasks if t.status in active_statuses][:limit_tasks]
    by_domain: dict[str, list[Any]] = {}
    rework_by_domain: dict[str, int] = {}

    for t in subset:
        try:
            eff = get_effective_domain_context(t.id, getattr(t, "owner_text", None))
            primary = (eff or {}).get("selected_primary_domain") or "other"
        except Exception:
            primary = "other"
        by_domain.setdefault(primary, []).append(t)
        if (getattr(t, "rework_cycles", 0) or 0) >= 1 or t.status == TaskStatus.REWORK.value:
            rework_by_domain[primary] = rework_by_domain.get(primary, 0) + 1

    signals = []
    for domain_key, task_list in sorted(by_domain.items(), key=lambda x: -len(x[1]))[:limit_signals]:
        count = len(task_list)
        rework_count = rework_by_domain.get(domain_key, 0)
        reason = f"Активных задач в домене {domain_key}: {count}"
        if rework_count:
            reason += f"; rework: {rework_count}"
        signals.append({
            "domain_key": domain_key,
            "task_count": count,
            "rework_count": rework_count,
            "reason": reason,
            "explainable": True,
        })
    override_signals = []
    try:
        override_signals = get_domain_override_signals(limit=5)
    except Exception:
        pass
    project_domain_signals = []
    try:
        project_domain_signals = get_project_domain_signals(limit=5)
    except Exception:
        pass
    specialization_signals = []
    try:
        specialization_signals = get_specialization_signals(limit=limit_signals)
    except Exception:
        pass
    refinement_signals = []
    try:
        from app.services.domain_specialization_analytics import get_refinement_signals
        refinement_signals = get_refinement_signals(window_days=30, limit=limit_signals)
    except Exception:
        pass
    pending_refinement = {}
    try:
        pending_refinement = get_pending_refinement_attention()
    except Exception:
        pass
    project_domain_lifecycle_signals = []
    try:
        from app.services.project_domain_lifecycle import get_project_domain_drift_signals, get_project_domain_instability_signals
        drift = get_project_domain_drift_signals(window_days=30, limit=5)
        instab = get_project_domain_instability_signals(window_days=30, limit=5)
        for lc in drift:
            project_domain_lifecycle_signals.append({"type": "project_domain_drift", "project_key": lc.get("project_key"), "reason": lc.get("reason", "Доминанта сменилась")})
        for lc in instab:
            project_domain_lifecycle_signals.append({"type": "project_domain_instability", "project_key": lc.get("project_key"), "reason": lc.get("reason", "Нестабильный профиль")})
    except Exception:
        pass
    project_domain_evolution_signals = []
    try:
        from app.services.project_domain_evolution_refinement import list_project_domain_attention_items
        attn = list_project_domain_attention_items(window_days=30, limit=10)
        for it in attn:
            project_domain_evolution_signals.append({
                "type": "project_domain_evolution_attention",
                "project_key": it.get("project_key"),
                "refinement_class": it.get("refinement_class"),
                "owner_answer": it.get("owner_answer"),
                "reason": it.get("attention_reason", ""),
            })
    except Exception:
        pass
    return {
        "items": signals,
        "count": len(signals),
        "explainable": True,
        "override_signals": override_signals,
        "project_domain_signals": project_domain_signals,
        "project_domain_lifecycle_signals": project_domain_lifecycle_signals,
        "project_domain_evolution_signals": project_domain_evolution_signals,
        "specialization_signals": specialization_signals,
        "refinement_signals": refinement_signals,
        "pending_refinement_proposals": pending_refinement,
    }


def get_pending_refinement_attention() -> dict[str, Any]:
    """
    Phase 10.6/10.7: сводка по pending refinement proposals для рекомендаций.
    Phase 10.7: добавляет patchable — accepted с safe patch candidate, high_risk, failed_validation.
    """
    try:
        from app.services.refinement_proposals import list_refinement_proposals
    except ImportError:
        return {}
    proposed = list_refinement_proposals(status="proposed", limit=100)
    accepted = list_refinement_proposals(status="accepted", limit=100)
    pending_count = len(proposed)
    accepted_count = len(accepted)
    high = sum(1 for p in proposed + accepted if p.get("severity") == "medium")
    out = {
        "pending_count": pending_count,
        "accepted_not_applied_count": accepted_count,
        "high_severity_count": high,
        "message": f"Pending refinement: {pending_count} на ревью, {accepted_count} приняты (к применению)" if (pending_count or accepted_count) else "",
    }
    try:
        from app.services.registry_patch_builder import build_patch_candidate
        from app.services.registry_patch_apply import validate_patch_candidate
        safe_patchable = 0
        high_risk_count = 0
        failed_validation_count = 0
        for p in accepted[:20]:
            pid = p.get("proposal_id")
            if not pid:
                continue
            patch = build_patch_candidate(pid)
            if patch.get("error"):
                continue
            if not patch.get("apply_allowed"):
                high_risk_count += 1
                continue
            val = validate_patch_candidate(pid)
            if val.get("validation_status") == "ok":
                safe_patchable += 1
            elif val.get("validation_status") == "error":
                failed_validation_count += 1
        out["safe_patch_candidates_count"] = safe_patchable
        out["high_risk_not_auto_applicable_count"] = high_risk_count
        out["failed_patch_validation_count"] = failed_validation_count
        if safe_patchable or failed_validation_count or high_risk_count:
            out["patch_message"] = (
                f"Safe patch: {safe_patchable} к apply. "
                f"Failed validation: {failed_validation_count}. High-risk (manual): {high_risk_count}"
            )
        try:
            from app.services.patch_coverage import get_patch_coverage_summary
            cov = get_patch_coverage_summary(status="accepted", limit=50)
            out["patchable_count"] = cov.get("patchable_count", safe_patchable)
            out["manual_only_count"] = cov.get("manual_only_count", high_risk_count)
            out["patchable_types"] = cov.get("patchable_types", [])
        except Exception:
            pass
    except Exception:
        pass
    return out


def get_specialization_signals(limit: int = 5) -> list[dict[str, Any]]:
    """
    Phase 10.4: specialization-related recommendation signals (explainable).
    - specialization_fallback_hotspot: домен/задачи, где часто используется fallback-профиль
    - specialization_mismatch_signal: домен задан, но specialization остаётся general
    - weak_execution_lane_signal: много задач с general execution lane по домену
    """
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
        from app.services.agent_specializations import suggest_specialization
    except ImportError:
        return []

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    active_statuses = {
        TaskStatus.NEW.value, TaskStatus.TRIAGED.value, TaskStatus.IN_PIPELINE.value,
        TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value,
        TaskStatus.WAIT_OWNER.value, TaskStatus.REWORK.value, TaskStatus.NEED_INFO.value,
        TaskStatus.APPROVED_WAIT_MERGE.value,
    }
    subset = [t for t in tasks if t.status in active_statuses][:30]
    fallback_by_domain: dict[str, int] = defaultdict(int)
    mismatch_task_ids: list[int] = []
    general_count = 0
    for t in subset:
        try:
            eff = get_effective_domain_context(t.id, getattr(t, "owner_text", None))
            primary = (eff or {}).get("selected_primary_domain") or "general"
        except Exception:
            primary = "general"
        try:
            sel = suggest_specialization(t.id, "pipeline", getattr(t, "owner_text", None))
            fallback = sel.get("fallback_used", False)
            spec_key = (sel.get("selected_specialization") or {}).get("specialization_key", "")
            if fallback:
                fallback_by_domain[primary] = fallback_by_domain.get(primary, 0) + 1
            if primary != "general" and spec_key and spec_key.startswith("general_"):
                mismatch_task_ids.append(t.id)
            if spec_key.startswith("general_"):
                general_count += 1
        except Exception:
            pass
    signals = []
    for domain_key, count in sorted(fallback_by_domain.items(), key=lambda x: -x[1])[:3]:
        if count >= 2:
            signals.append({
                "signal_type": "specialization_fallback_hotspot",
                "domain_key": domain_key,
                "task_count": count,
                "reason": f"По домену {domain_key} часто используется fallback-профиль ({count} задач)",
                "suggested_action": f"Проверить реестр специализаций для домена {domain_key}",
                "explainable": True,
            })
    for tid in mismatch_task_ids[:3]:
        signals.append({
            "signal_type": "specialization_mismatch_signal",
            "task_id": tid,
            "reason": "Домен задан, но выбран general-профиль",
            "suggested_action": "Проверить /task_specialization или override домена",
            "explainable": True,
        })
    if general_count >= 5 and len(subset) >= 5:
        pct = round(100 * general_count / max(len(subset), 1))
        signals.append({
            "signal_type": "weak_execution_lane_signal",
            "reason": f"Много задач с general execution lane ({general_count}, ~{pct}% активных)",
            "suggested_action": "Уточнить домены задач или расширить реестр специализаций",
            "explainable": True,
        })
    return signals[:limit]


def get_project_domain_signals(limit: int = 5) -> list[dict[str, Any]]:
    """
    Phase 10.3: project-domain signals — override-heavy projects, mismatch.
    """
    try:
        from app.services.project_domain_mapping import list_project_domain_profiles
    except ImportError:
        return []
    profiles = list_project_domain_profiles(limit=20)
    signals = []
    for p in profiles:
        if not p.get("mismatch_signals"):
            continue
        for m in p["mismatch_signals"]:
            signals.append({
                "project_key": p.get("project_key"),
                "signal_type": m.get("type", "mismatch"),
                "reason": m.get("reason", ""),
                "explainable": True,
            })
    return signals[:limit]


def get_domain_override_signals(limit: int = 5) -> list[dict[str, Any]]:
    """
    Phase 10.2: сигналы по override — mismatch (auto vs override) и manual correction.
    """
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
        from app.services.domain_override_store import get_override
        from app.services.domain_triage import build_task_domain_metadata
    except ImportError:
        return []

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    active_statuses = {
        TaskStatus.NEW.value, TaskStatus.TRIAGED.value, TaskStatus.IN_PIPELINE.value,
        TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value,
        TaskStatus.WAIT_OWNER.value, TaskStatus.REWORK.value, TaskStatus.NEED_INFO.value,
        TaskStatus.APPROVED_WAIT_MERGE.value,
    }
    subset = [t for t in tasks if t.status in active_statuses]
    signals = []
    for t in subset:
        ov = get_override(t.id)
        if not ov or not ov.get("override_active"):
            continue
        effective = get_effective_domain_context(t.id, getattr(t, "owner_text", None))
        override_domain = effective.get("selected_primary_domain")
        previous = ov.get("previous_primary_domain")
        try:
            auto_meta = build_task_domain_metadata(getattr(t, "owner_text", None) or "")
            auto_domain = auto_meta.get("primary_domain")
        except Exception:
            auto_domain = None
        signals.append({
            "signal_type": "manual_domain_correction_signal",
            "task_id": t.id,
            "reason": f"Owner задал домен {override_domain}",
            "override_domain": override_domain,
            "explainable": True,
        })
        if auto_domain and auto_domain != override_domain:
            signals.append({
                "signal_type": "override_mismatch_signal",
                "task_id": t.id,
                "reason": f"Авто: {auto_domain}, owner выбрал: {override_domain}",
                "auto_domain": auto_domain,
                "override_domain": override_domain,
                "explainable": True,
            })
    return signals[:limit]
