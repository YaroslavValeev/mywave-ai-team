# Слияние v0-классификатора с контекстом v1
from __future__ import annotations

import os

from app.intake.context_resolver import resolve_context
from app.intake.memory_retriever import MemoryBundle, retrieve_memory
from app.intake.schemas import NormalizeIntakeRequest, NormalizeIntakeResponse
from app.intake.task_matcher import CONTINUATION_RE, match_related_task
from app.storage.repositories import TaskRepository


def _threshold() -> float:
    raw = os.getenv("INTAKE_ATTACH_SIMILARITY_THRESHOLD", "0.26").strip()
    try:
        return max(0.05, min(0.95, float(raw)))
    except ValueError:
        return 0.26


def apply_intake_v1(
    base: NormalizeIntakeResponse,
    req: NormalizeIntakeRequest,
    repo: TaskRepository,
    *,
    combined_text: str,
    reply_task_id: int | None,
) -> NormalizeIntakeResponse:
    """Обогащает ответ полями v1; при необходимости меняет decision на attach / clarify."""
    if base.decision == "reject":
        return base.model_copy(
            update={
                "decision_reason": "classifier_reject",
                "memory_used": False,
            }
        )

    ctx = resolve_context(
        repo,
        combined_text=combined_text,
        reply_task_id=reply_task_id,
        project_id_hint=req.project_id_hint,
    )

    if ctx.ambiguous_project_ids:
        names = []
        for pid_a in ctx.ambiguous_project_ids[:5]:
            p = repo.get_project(pid_a)
            names.append(f"• {p.name} (id {pid_a})" if p else f"• id {pid_a}")
        questions = [
            "Не уверен, к какому проекту отнести ввод. Уточните название или укажите project_id_hint (API).",
            *names,
        ]
        new_brief = base.task_brief.model_copy(
            update={
                "project_id": None,
                "project_name": "",
                "related_task_id": None,
                "context_summary": "",
                "memory_refs": [],
                "brief_confidence": 0.35,
            }
        )
        return base.model_copy(
            update={
                "task_brief": new_brief,
                "decision": "clarify",
                "needs_clarification": True,
                "clarifying_questions": questions[:5],
                "confidence": min(base.confidence, 0.55),
                "matched_project_id": None,
                "matched_task_id": None,
                "similarity_score": None,
                "decision_reason": "ambiguous_projects",
                "memory_used": False,
            }
        )

    mem = MemoryBundle()
    if ctx.project_id is not None:
        mem = retrieve_memory(repo, project_id=ctx.project_id, query_text=combined_text)

    m_tid, similarity, match_reason = match_related_task(
        repo,
        combined_text=combined_text,
        reply_task_id=reply_task_id,
        candidate_project_id=ctx.project_id,
        threshold=_threshold(),
    )

    decision = base.decision
    needs_clar = base.needs_clarification
    questions = list(base.clarifying_questions)
    conf = base.confidence
    decision_reason = f"classifier:{base.decision};ctx:{ctx.reason};match:{match_reason}"

    proj_id = ctx.project_id
    proj_name = ctx.project_name or ""

    rel_task_id: int | None = None
    if decision == "attach":
        rel_task_id = reply_task_id or m_tid

    brief_src = base.task_brief
    thr = _threshold()
    cont = bool(CONTINUATION_RE.search(combined_text))
    if (
        decision == "create"
        and m_tid is not None
        and reply_task_id is None
        and (similarity >= thr or (cont and similarity >= 0.14))
    ):
        decision = "attach"
        needs_clar = False
        questions = []
        rel_task_id = m_tid
        decision_reason = f"task_matcher_attach;{match_reason};sim={similarity:.2f}"
        t = repo.get_task(m_tid)
        if t and t.project_id:
            proj_id = t.project_id
            pr = repo.get_project(t.project_id)
            if pr:
                proj_name = pr.name
        brief_src = base.task_brief.model_copy(
            update={
                "title": base.task_brief.title or f"Дополнение к миссии #{m_tid}",
                "goal": base.task_brief.goal or "Продолжить существующую миссию",
            }
        )
        conf = max(conf, similarity, 0.55)
    elif decision == "attach" and rel_task_id:
        t = repo.get_task(rel_task_id)
        if t and t.project_id:
            proj_id = t.project_id
            pr = repo.get_project(t.project_id)
            if pr:
                proj_name = pr.name

    context_bits: list[str] = []
    if proj_name:
        context_bits.append(f"Проект: {proj_name} (id={proj_id})")
    if ctx.reply_task:
        context_bits.append(f"Реплай относится к миссии #{ctx.reply_task.id}")
    if mem.snippets:
        context_bits.append("Релевантная память:")
        for s in mem.snippets[:3]:
            context_bits.append(f"• {s}")

    new_brief = brief_src.model_copy(
        update={
            "project_id": proj_id,
            "project_name": proj_name,
            "related_task_id": rel_task_id,
            "context_summary": "\n".join(context_bits)[:6000],
            "memory_refs": mem.refs[:12],
            "brief_confidence": similarity if m_tid else 0.82,
        }
    )

    return base.model_copy(
        update={
            "task_brief": new_brief,
            "decision": decision,
            "needs_clarification": needs_clar,
            "clarifying_questions": questions[:5],
            "confidence": min(1.0, conf),
            "matched_project_id": proj_id,
            "matched_task_id": m_tid or reply_task_id,
            "similarity_score": similarity if m_tid else None,
            "decision_reason": decision_reason,
            "memory_used": mem.used,
        },
    )
