# Резолв проекта и черновика «где мы в системе» (Smart Intake v1)
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.storage.models import Project, Task
from app.storage.repositories import TaskRepository


@dataclass
class ResolvedContext:
    project_id: int | None = None
    project_name: str = ""
    reply_task: Task | None = None
    ambiguous_project_ids: list[int] = field(default_factory=list)
    reason: str = ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _projects_by_keyword(text: str, projects: list[Project]) -> list[Project]:
    low = _norm(text)
    if not low:
        return []
    hits: list[Project] = []
    for p in projects:
        name = _norm(p.name)
        slug = _norm(p.slug)
        if len(name) >= 3 and name in low:
            hits.append(p)
            continue
        if len(slug) >= 3 and slug.replace("-", " ") in low.replace("-", " "):
            hits.append(p)
            continue
        # «проект X» / project X
        if name and re.search(rf"\b{re.escape(name[: min(24, len(name))])}\b", low):
            hits.append(p)
    # уникальные по id
    seen: set[int] = set()
    out: list[Project] = []
    for p in hits:
        if p.id in seen:
            continue
        seen.add(p.id)
        out.append(p)
    return out


def resolve_context(
    repo: TaskRepository,
    *,
    combined_text: str,
    reply_task_id: int | None,
    project_id_hint: int | None,
) -> ResolvedContext:
    """Определить проект и (если есть) задачу из реплая."""
    projects = repo.list_active_projects(limit=80)

    if project_id_hint is not None:
        p = repo.get_project(project_id_hint)
        if p:
            return ResolvedContext(
                project_id=p.id,
                project_name=p.name,
                reason="project_id_hint",
            )
        return ResolvedContext(reason="hint_project_not_found")

    if reply_task_id is not None:
        task = repo.get_task(reply_task_id)
        if task:
            pid = task.project_id
            pname = ""
            if pid:
                pr = repo.get_project(pid)
                if pr:
                    pname = pr.name
            return ResolvedContext(
                project_id=pid,
                project_name=pname,
                reply_task=task,
                reason="telegram_reply_task",
            )
        return ResolvedContext(reason="reply_task_not_found")

    hits = _projects_by_keyword(combined_text, projects)
    if len(hits) > 1:
        return ResolvedContext(
            ambiguous_project_ids=[p.id for p in hits],
            reason="ambiguous_project_keywords",
        )
    if len(hits) == 1:
        p = hits[0]
        return ResolvedContext(project_id=p.id, project_name=p.name, reason="project_name_in_text")

    default = repo.get_default_project()
    return ResolvedContext(
        project_id=default.id,
        project_name=default.name,
        reason="default_project",
    )
