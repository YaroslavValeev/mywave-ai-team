# app/services/project_domain_lifecycle.py — Phase 10.8: project-domain evolution and lifecycle
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.project_queries import _tasks_for_project, list_projects
from app.services.project_domain_mapping import get_project_domain_profile

MIN_TASKS = 3
DOMINANT_MIN_SHARE = 0.55
SECONDARY_MIN_SHARE = 0.15


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _task_created_at(task: Any) -> datetime:
    c = getattr(task, "created_at", None)
    if c is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _to_utc(c) or datetime.min.replace(tzinfo=timezone.utc)


def _distribution_for_tasks(tasks: list[Any]) -> dict[str, int]:
    """Распределение доменов по задачам (effective domain)."""
    dist: dict[str, int] = defaultdict(int)
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
    except ImportError:
        return dict(dist)
    for t in tasks:
        try:
            eff = get_effective_domain_context(getattr(t, "id", None), getattr(t, "owner_text", None))
            primary = (eff or {}).get("selected_primary_domain") or "other"
            dist[primary] += 1
        except Exception:
            dist["other"] += 1
    return dict(dist)


def _dominant_from_distribution(dist: dict[str, int]) -> str | None:
    if not dist:
        return None
    return max(dist, key=lambda d: dist[d])


def _compute_lifecycle_state(
    project_key: str,
    previous_dist: dict[str, int],
    current_dist: dict[str, int],
    profile: dict[str, Any],
) -> tuple[str, str, bool, bool, bool]:
    """
    Возвращает (lifecycle_state, explanation, drift_signal, diversification_signal, instability_signal).
    """
    prev_dom = _dominant_from_distribution(previous_dist)
    curr_dom = _dominant_from_distribution(current_dist)
    total_prev = sum(previous_dist.values())
    total_curr = sum(current_dist.values())
    total = total_prev + total_curr

    if total < MIN_TASKS:
        return (
            "weak_signal",
            "Мало задач в окне — профиль домена не определён.",
            False,
            False,
            False,
        )

    mismatch = profile.get("mismatch_signals") or []
    override_heavy = any(m.get("type") == "override_heavy" or m.get("type") == "correction_rate" for m in mismatch)
    if override_heavy:
        return (
            "override_heavy",
            "Высокая доля ручной коррекции домена по проекту.",
            False,
            False,
            False,
        )

    # Достаточно задач в обеих половинах и сменился доминант
    drift = total_prev >= 2 and total_curr >= 2 and prev_dom and curr_dom and prev_dom != curr_dom
    if drift:
        return (
            "drifting",
            f"Доминирующий домен сменился за период: {prev_dom} → {curr_dom}.",
            True,
            False,
            False,
        )

    # Два домена устойчиво значимы в current
    if current_dist:
        total_cur = sum(current_dist.values())
        sorted_domains = sorted(current_dist.items(), key=lambda x: -x[1])
        if len(sorted_domains) >= 2:
            first_share = sorted_domains[0][1] / total_cur if total_cur else 0
            second_share = sorted_domains[1][1] / total_cur if total_cur else 0
            if first_share >= SECONDARY_MIN_SHARE and second_share >= SECONDARY_MIN_SHARE and first_share < 0.75:
                return (
                    "stable_multi_domain",
                    "Два домена устойчиво значимы в проекте.",
                    False,
                    True,
                    False,
                )

    # Нестабильность: низкая уверенность и много override
    confidence = profile.get("mapping_confidence", "medium")
    override_count = profile.get("override_count", 0)
    task_count = profile.get("task_count", 0)
    if confidence == "low" and task_count > 0 and (override_count / task_count) > 0.2:
        return (
            "unstable",
            "Нестабильный доменный профиль: частые коррекции или fallback.",
            False,
            False,
            True,
        )

    # Стабильный один домен
    if curr_dom and current_dist.get(curr_dom, 0) / (sum(current_dist.values()) or 1) >= DOMINANT_MIN_SHARE:
        return (
            "stable_single_domain",
            "Один домен стабильно доминирует в окне.",
            False,
            False,
            False,
        )

    if confidence == "low":
        return (
            "weak_signal",
            "Недостаточно данных для уверенного профиля.",
            False,
            False,
            True,
        )

    return (
        "stable_single_domain",
        "Один домен доминирует в окне.",
        False,
        False,
        False,
    )


def get_project_domain_lifecycle(project_key: str, window_days: int = 30) -> dict[str, Any]:
    """Lifecycle профиль проекта за окно: current/previous dominant, state, signals."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=window_days)
    mid = now - timedelta(days=window_days // 2)
    tasks = _tasks_for_project(project_key)
    tasks_in_window = [t for t in tasks if _task_created_at(t) >= since]
    previous_tasks = [t for t in tasks_in_window if _task_created_at(t) < mid]
    current_tasks = [t for t in tasks_in_window if _task_created_at(t) >= mid]

    previous_dist = _distribution_for_tasks(previous_tasks)
    current_dist = _distribution_for_tasks(current_tasks)
    profile = get_project_domain_profile(project_key)

    prev_dom = _dominant_from_distribution(previous_dist)
    curr_dom = _dominant_from_distribution(current_dist)
    state, explanation, drift, diversif, instability = _compute_lifecycle_state(
        project_key, previous_dist, current_dist, profile
    )

    stability = "changed" if (prev_dom and curr_dom and prev_dom != curr_dom) else "stable"
    if not prev_dom and not curr_dom:
        stability = "unknown"

    return {
        "project_key": project_key,
        "current_dominant_domain": curr_dom,
        "previous_dominant_domain": prev_dom,
        "dominant_domain_stability": stability,
        "domain_drift_signal": drift,
        "domain_diversification_signal": diversif,
        "domain_instability_signal": instability,
        "domain_mix": dict(current_dist),
        "lifecycle_state": state,
        "window_days": window_days,
        "updated_at": now.isoformat(),
        "reason": explanation,
        "task_count_previous": sum(previous_dist.values()),
        "task_count_current": sum(current_dist.values()),
    }


def list_project_domain_lifecycles(window_days: int = 30, limit: int = 50) -> list[dict[str, Any]]:
    """Список lifecycle по всем проектам."""
    projects = list_projects(limit=limit)
    keys = [p.get("project_key") for p in projects.get("items", []) if p.get("project_key")]
    return [get_project_domain_lifecycle(k, window_days) for k in keys]


def get_project_domain_drift_signals(window_days: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Проекты с drift (смена доминанты)."""
    lifecycles = list_project_domain_lifecycles(window_days=window_days, limit=100)
    drifting = [lc for lc in lifecycles if lc.get("domain_drift_signal")]
    drifting.sort(key=lambda x: -(x.get("task_count_current", 0) + x.get("task_count_previous", 0)))
    return drifting[:limit]


def get_project_domain_diversification_signals(window_days: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Проекты с diversification (stable_multi_domain)."""
    lifecycles = list_project_domain_lifecycles(window_days=window_days, limit=100)
    multi = [lc for lc in lifecycles if lc.get("domain_diversification_signal")]
    multi.sort(key=lambda x: -(x.get("task_count_current", 0) + x.get("task_count_previous", 0)))
    return multi[:limit]


def get_project_domain_instability_signals(window_days: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Проекты с instability или override_heavy."""
    lifecycles = list_project_domain_lifecycles(window_days=window_days, limit=100)
    unstable = [lc for lc in lifecycles if lc.get("domain_instability_signal") or lc.get("lifecycle_state") in ("unstable", "override_heavy")]
    unstable.sort(key=lambda x: -(x.get("task_count_current", 0) + x.get("task_count_previous", 0)))
    return unstable[:limit]


def get_cross_project_domain_lifecycle_summary(window_days: int = 30) -> dict[str, Any]:
    """Сводка по lifecycle по всем проектам: дрифтующие, override-heavy, нестабильные."""
    drift = get_project_domain_drift_signals(window_days=window_days, limit=10)
    diversif = get_project_domain_diversification_signals(window_days=window_days, limit=10)
    instab = get_project_domain_instability_signals(window_days=window_days, limit=10)
    lifecycles = list_project_domain_lifecycles(window_days=window_days, limit=100)
    by_state: dict[str, int] = defaultdict(int)
    for lc in lifecycles:
        by_state[lc.get("lifecycle_state", "unknown")] += 1
    return {
        "window_days": window_days,
        "drifting_projects_count": len(drift),
        "diversification_projects_count": len(diversif),
        "unstable_or_override_heavy_count": len(instab),
        "by_lifecycle_state": dict(by_state),
        "drifting": drift,
        "diversification": diversif,
        "unstable_or_override_heavy": instab,
        "summary": f"Дрифт: {len(drift)}, мульти-домен: {len(diversif)}, нестабильные/override: {len(instab)}",
    }
