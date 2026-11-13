# app/services/role_domain_recommendations.py — Phase 10.3: role-domain recommendations (explainable)
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.storage.repositories import get_session_factory, TaskRepository
from app.storage.models import TaskStatus

ACTIVE_STATUSES = {
    TaskStatus.NEW.value, TaskStatus.TRIAGED.value, TaskStatus.IN_PIPELINE.value,
    TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value,
    TaskStatus.WAIT_OWNER.value, TaskStatus.REWORK.value, TaskStatus.NEED_INFO.value,
    TaskStatus.APPROVED_WAIT_MERGE.value,
}


def _tasks_with_effective_domain() -> list[tuple[Any, str]]:
    """Задачи с их effective primary domain. Возвращает [(task, domain_key), ...]."""
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
    except ImportError:
        return []
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        tasks = repo.get_all_tasks()
    out = []
    for t in tasks:
        try:
            eff = get_effective_domain_context(getattr(t, "id", None), getattr(t, "owner_text", None))
            primary = (eff or {}).get("selected_primary_domain") or "other"
            out.append((t, primary))
        except Exception:
            out.append((t, "other"))
    return out


def get_owner_domain_recommendations(limit_domains: int = 5) -> dict[str, Any]:
    """Рекомендации по доменам для owner: backlog, rework, override mismatches."""
    pairs = _tasks_with_effective_domain()
    pending_by_d: dict[str, int] = defaultdict(int)
    rework_by_d: dict[str, int] = defaultdict(int)
    override_by_d: dict[str, int] = defaultdict(int)
    for t, d in pairs:
        if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value):
            pending_by_d[d] += 1
        if (getattr(t, "rework_cycles", 0) or 0) >= 1 or t.status == TaskStatus.REWORK.value:
            rework_by_d[d] += 1
        try:
            from app.services.domain_override_store import get_override
            if get_override(getattr(t, "id", 0)):
                override_by_d[d] += 1
        except Exception:
            pass
    pressure = []
    for dom in set(pending_by_d) | set(rework_by_d) | set(override_by_d):
        p, rw, ov = pending_by_d.get(dom, 0), rework_by_d.get(dom, 0), override_by_d.get(dom, 0)
        if p or rw or ov:
            pressure.append({
                "domain_key": dom,
                "pending_count": p,
                "rework_count": rw,
                "override_count": ov,
                "reason": f"pending: {p}, rework: {rw}, override: {ov}",
            })
    pressure.sort(key=lambda x: -(x["pending_count"] + x["rework_count"] * 2 + x["override_count"]))
    recommended = [p["domain_key"] for p in pressure[:limit_domains]]
    why = "Наибольшее внимание требуют домены с backlog approvals, rework и ручными правками домена."
    action = "Разобрать approvals и rework по приоритетным доменам; при частых override — уточнить триаж доменов."
    evidence = "; ".join([f"{p['domain_key']}: pending {p['pending_count']}, rework {p['rework_count']}, override {p['override_count']}" for p in pressure[:3]]) or "Нет данных"
    return {
        "role_key": "owner",
        "recommended_domains": recommended,
        "current_domain_pressure": pressure[:limit_domains],
        "domain_gap_signals": [],
        "why_this_role_needs_it": why,
        "recommended_action": action,
        "evidence_summary": evidence,
    }


def get_operator_domain_recommendations(limit_domains: int = 5) -> dict[str, Any]:
    """Рекомендации по доменам для operator: где блокеры и long-running."""
    try:
        from app.services.owner_insights import get_blockers_summary, get_long_running_summary
    except ImportError:
        return _empty_role_rec("operator")
    blockers = get_blockers_summary(limit=20)
    long_running = get_long_running_summary(limit=20)
    by_d: dict[str, int] = defaultdict(int)
    for i in blockers.get("items", []) + long_running.get("items", []):
        t = i.get("task") if isinstance(i, dict) else None
        if not t:
            continue
        try:
            from app.services.workflow_domain_context import get_effective_domain_context
            eff = get_effective_domain_context(getattr(t, "id", None), getattr(t, "owner_text", None))
            d = (eff or {}).get("selected_primary_domain") or "other"
            by_d[d] += 1
        except Exception:
            by_d["other"] += 1
    pressure = [{"domain_key": d, "count": c, "reason": f"блокеры/зависшие: {c}"} for d, c in sorted(by_d.items(), key=lambda x: -x[1])]
    recommended = [p["domain_key"] for p in pressure[:limit_domains]]
    return {
        "role_key": "operator",
        "recommended_domains": recommended,
        "current_domain_pressure": pressure[:limit_domains],
        "domain_gap_signals": [],
        "why_this_role_needs_it": "Operator должен снимать блокеры и зависшие задачи; по доменам видно, где они концентрируются.",
        "recommended_action": "Проверить runtime и логи по доменам с наибольшим числом блокеров.",
        "evidence_summary": "; ".join([f"{p['domain_key']}: {p['count']}" for p in pressure[:3]]) or "Нет блокеров/ long-running",
    }


def get_executor_domain_recommendations(limit_domains: int = 5) -> dict[str, Any]:
    """Рекомендации по доменам для executor: активная работа и артефакты."""
    pairs = [(t, d) for t, d in _tasks_with_effective_domain() if t.status in ACTIVE_STATUSES]
    by_d: dict[str, int] = defaultdict(int)
    for t, d in pairs:
        by_d[d] += 1
    pressure = [{"domain_key": d, "count": c, "reason": f"активных задач: {c}"} for d, c in sorted(by_d.items(), key=lambda x: -x[1])]
    recommended = [p["domain_key"] for p in pressure[:limit_domains]]
    return {
        "role_key": "executor",
        "recommended_domains": recommended,
        "current_domain_pressure": pressure[:limit_domains],
        "domain_gap_signals": [],
        "why_this_role_needs_it": "Executor выполняет активные задачи; по доменам видно, где больше всего работы.",
        "recommended_action": "Фокус на доменах с наибольшим числом активных задач.",
        "evidence_summary": "; ".join([f"{p['domain_key']}: {p['count']}" for p in pressure[:3]]) or "Нет активных задач",
    }


def get_reviewer_domain_recommendations(limit_domains: int = 5) -> dict[str, Any]:
    """Рекомендации по доменам для reviewer: pending approvals и decision queue."""
    pairs = _tasks_with_effective_domain()
    pending = [(t, d) for t, d in pairs if t.status in (TaskStatus.WAIT_OWNER.value, TaskStatus.APPROVED_WAIT_MERGE.value)]
    by_d: dict[str, int] = defaultdict(int)
    for t, d in pending:
        by_d[d] += 1
    pressure = [{"domain_key": d, "count": c, "reason": f"ожидают решения: {c}"} for d, c in sorted(by_d.items(), key=lambda x: -x[1])]
    recommended = [p["domain_key"] for p in pressure[:limit_domains]]
    return {
        "role_key": "reviewer",
        "recommended_domains": recommended,
        "current_domain_pressure": pressure[:limit_domains],
        "domain_gap_signals": [],
        "why_this_role_needs_it": "Reviewer закрывает очередь решений; по доменам видно, где сконцентрированы approvals.",
        "recommended_action": "Разобрать очередь по доменам с наибольшим числом ожидающих решений.",
        "evidence_summary": "; ".join([f"{p['domain_key']}: {p['count']}" for p in pressure[:3]]) or "Нет ожидающих решений",
    }


def _empty_role_rec(role_key: str) -> dict[str, Any]:
    return {
        "role_key": role_key,
        "recommended_domains": [],
        "current_domain_pressure": [],
        "domain_gap_signals": [],
        "why_this_role_needs_it": "",
        "recommended_action": "",
        "evidence_summary": "Нет данных",
    }


def get_role_domain_recommendations(role_key: str, limit_domains: int = 5) -> dict[str, Any]:
    """Единая точка: рекомендации по доменам для роли."""
    if role_key == "owner":
        return get_owner_domain_recommendations(limit_domains=limit_domains)
    if role_key == "operator":
        return get_operator_domain_recommendations(limit_domains=limit_domains)
    if role_key == "executor":
        return get_executor_domain_recommendations(limit_domains=limit_domains)
    if role_key == "reviewer":
        return get_reviewer_domain_recommendations(limit_domains=limit_domains)
    return _empty_role_rec(role_key)
