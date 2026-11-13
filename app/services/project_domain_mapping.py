# app/services/project_domain_mapping.py — Phase 10.3: project–domain mapping (explainable)
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.project_queries import _tasks_for_project, list_projects
from app.storage.models import TaskStatus

ACTIVE_STATUSES = {
    TaskStatus.NEW.value, TaskStatus.TRIAGED.value, TaskStatus.IN_PIPELINE.value,
    TaskStatus.IN_ROUNDTABLE.value, TaskStatus.IN_COURT.value,
    TaskStatus.WAIT_OWNER.value, TaskStatus.REWORK.value, TaskStatus.NEED_INFO.value,
    TaskStatus.APPROVED_WAIT_MERGE.value,
}
SECONDARY_MIN_COUNT = 2
SECONDARY_MIN_SHARE = 0.15
OVERRIDE_HEAVY_THRESHOLD = 2
CORRECTION_RATE_THRESHOLD = 0.30


def get_project_domain_profile(project_key: str) -> dict[str, Any]:
    """Профиль доменов по проекту: dominant, distribution, mismatch, confidence."""
    tasks = _tasks_for_project(project_key)
    subset = [t for t in tasks if t.status in ACTIVE_STATUSES]
    return _build_profile(project_key, subset)


def _build_profile(project_key: str, tasks: list[Any]) -> dict[str, Any]:
    if not tasks:
        return {
            "project_key": project_key,
            "dominant_domain": None,
            "secondary_domains": [],
            "domain_distribution": {},
            "domain_signal_source": "tasks",
            "mapping_confidence": "low",
            "mismatch_signals": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "task_count": 0,
            "override_count": 0,
        }
    try:
        from app.services.workflow_domain_context import get_effective_domain_context
        from app.services.domain_override_store import get_override
    except ImportError:
        return {
            "project_key": project_key,
            "dominant_domain": None,
            "secondary_domains": [],
            "domain_distribution": {},
            "domain_signal_source": "tasks",
            "mapping_confidence": "low",
            "mismatch_signals": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "task_count": len(tasks),
            "override_count": 0,
        }
    distribution: dict[str, int] = {}
    override_count = 0
    for t in tasks:
        try:
            eff = get_effective_domain_context(getattr(t, "id", None), getattr(t, "owner_text", None))
            primary = (eff or {}).get("selected_primary_domain") or "other"
            distribution[primary] = distribution.get(primary, 0) + 1
            if (eff or {}).get("domain_override"):
                override_count += 1
        except Exception:
            distribution["other"] = distribution.get("other", 0) + 1
    total = len(tasks)
    dominant = max(distribution, key=lambda d: distribution[d]) if distribution else None
    dominant_count = distribution.get(dominant, 0) if dominant else 0
    secondary = [
        d for d, c in distribution.items()
        if d != dominant and c >= SECONDARY_MIN_COUNT and (c / total) >= SECONDARY_MIN_SHARE
    ][:3]
    if total < 3 or (dominant_count / total) < 0.40:
        confidence = "low"
    elif total >= 10 and (dominant_count / total) >= 0.60:
        confidence = "high"
    else:
        confidence = "medium"
    mismatch_signals: list[dict[str, Any]] = []
    if override_count >= OVERRIDE_HEAVY_THRESHOLD:
        mismatch_signals.append({
            "type": "override_heavy",
            "reason": f"{override_count} задач с ручным override домена",
            "override_count": override_count,
        })
    if total > 0 and (override_count / total) > CORRECTION_RATE_THRESHOLD:
        mismatch_signals.append({
            "type": "correction_rate",
            "reason": f"Высокий процент ручной коррекции домена ({override_count}/{total})",
        })
    return {
        "project_key": project_key,
        "dominant_domain": dominant,
        "secondary_domains": secondary,
        "domain_distribution": dict(distribution),
        "domain_signal_source": "tasks",
        "mapping_confidence": confidence,
        "mismatch_signals": mismatch_signals,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "task_count": total,
        "override_count": override_count,
    }


def list_project_domain_profiles(limit: int = 50) -> list[dict[str, Any]]:
    """Список project-domain профилей по всем проектам."""
    projects = list_projects(limit=limit)
    keys = [p.get("project_key") for p in projects.get("items", []) if p.get("project_key")]
    out = []
    for k in keys:
        out.append(get_project_domain_profile(k))
    return out[:limit]


def get_project_dominant_domain(project_key: str) -> str | None:
    """Доминирующий домен проекта (краткий ответ)."""
    profile = get_project_domain_profile(project_key)
    return profile.get("dominant_domain")


def get_project_domain_distribution(project_key: str) -> dict[str, int]:
    """Распределение доменов по проекту."""
    profile = get_project_domain_profile(project_key)
    return profile.get("domain_distribution", {})


def get_project_domain_mismatch_signals(project_key: str) -> list[dict[str, Any]]:
    """Сигналы расхождения по проекту (override_heavy, correction_rate)."""
    profile = get_project_domain_profile(project_key)
    return profile.get("mismatch_signals", [])


def get_cross_project_domain_summary() -> dict[str, Any]:
    """Сводка по доменам по всем проектам: какой домен где доминирует, топ проектов по домену."""
    profiles = list_project_domain_profiles(limit=50)
    by_domain: dict[str, list[str]] = {}
    for p in profiles:
        dom = p.get("dominant_domain")
        if dom:
            by_domain.setdefault(dom, []).append(p.get("project_key", ""))
    return {
        "project_profiles_count": len(profiles),
        "domains_with_projects": {d: projs for d, projs in by_domain.items()},
        "summary": f"Учтено проектов: {len(profiles)}; доменов с доминантой: {len(by_domain)}",
    }
