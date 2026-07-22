# Сопоставление ввода с открытой задачей (продолжение vs новая)
from __future__ import annotations

import re

from app.storage.models import Task
from app.storage.repositories import TaskRepository

CONTINUATION_RE = re.compile(
    r"(добавь(\s+к)?\s+задач|к\s+задаче|в\s+той\s+задаче|продолж|обнови|уточни\s+по\s+миссии|"
    r"add\s+to(\s+the)?\s+task|update\s+the\s+task|follow[\s-]?up)",
    re.IGNORECASE,
)


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", s.lower()) if len(t) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def match_related_task(
    repo: TaskRepository,
    *,
    combined_text: str,
    reply_task_id: int | None,
    candidate_project_id: int | None,
    threshold: float,
) -> tuple[int | None, float, str]:
    """
    Возвращает (task_id, similarity 0..1, reason).
    reply_task_id — уже известная привязка (макс. уверенность).
    """
    if reply_task_id is not None:
        t = repo.get_task(reply_task_id)
        if t:
            return reply_task_id, 1.0, "explicit_reply_or_structured_context"

    tasks = repo.recent_open_tasks(limit=20)
    if candidate_project_id is not None:
        tasks = [t for t in tasks if t.project_id == candidate_project_id] or tasks

    low = combined_text.lower()
    cont_hit = bool(CONTINUATION_RE.search(combined_text))
    q = _tokens(combined_text)
    best_id: int | None = None
    best_sc = 0.0

    for t in tasks:
        blob = f"{t.owner_text or ''}\n{t.summary or ''}"
        sc = jaccard(q, _tokens(blob))
        if cont_hit:
            sc = min(1.0, sc + 0.12)
        if sc > best_sc:
            best_sc = sc
            best_id = t.id

    if best_id is None:
        return None, 0.0, "no_open_tasks"

    if best_sc >= threshold or (cont_hit and best_sc >= 0.14):
        return best_id, best_sc, "token_similarity_open_tasks"

    return None, best_sc, "below_threshold"
