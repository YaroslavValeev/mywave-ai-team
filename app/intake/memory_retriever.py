# Выборка памяти проекта для контекста intake (без pgvector в v1)
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.storage.models import MemoryEntry
from app.storage.repositories import TaskRepository


@dataclass
class MemoryBundle:
    refs: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)
    used: bool = False


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", s.lower()) if len(t) > 2}


def retrieve_memory(
    repo: TaskRepository,
    *,
    project_id: int,
    query_text: str,
    limit: int = 6,
) -> MemoryBundle:
    rows = repo.list_memory_entries(project_id, limit=40)
    if not rows:
        return MemoryBundle()

    qt = _tokens(query_text)
    if not qt:
        top = rows[:limit]
    else:
        scored: list[tuple[float, MemoryEntry]] = []
        for m in rows:
            mt = _tokens(m.content)
            inter = len(qt & mt)
            union = len(qt | mt) or 1
            overlap = inter / union
            scored.append((overlap, m))
        scored.sort(key=lambda x: -x[0])
        top = [m for _, m in scored[:limit] if _tokens(m.content) & qt][:limit] or [m for _, m in scored[:limit]]

    refs = [f"memory:{m.id}" for m in top]
    snippets = [(m.content or "").strip()[:400] for m in top]
    return MemoryBundle(refs=refs, snippets=snippets, used=True)
