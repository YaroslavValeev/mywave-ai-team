# Сборка ответа Smart Intake + логирование (без создания задачи)
from __future__ import annotations

import logging
import os
import time
from typing import Any, TYPE_CHECKING

from app.intake.classify import _combined_user_text, _resolve_reply_task_id, classify_intake
from app.intake.schemas import NormalizeIntakeRequest, NormalizeIntakeResponse, TaskBrief
from app.shared.redaction import redact

if TYPE_CHECKING:
    from app.storage.repositories import TaskRepository

logger = logging.getLogger(__name__)


def intake_v1_enabled() -> bool:
    return os.getenv("INTAKE_V1", "true").strip().lower() in {"1", "true", "yes"}


def task_brief_to_owner_text(brief: TaskBrief, *, original_input: str = "") -> str:
    """Читаемый owner_text для существующего triage (префикс #TASK + маркер трассировки)."""
    lines = [
        "#TASK [SmartIntake v1]",
        "",
        f"Заголовок: {brief.title.strip() or '(без заголовка)'}",
        f"Цель: {brief.goal.strip() or '(не указана)'}",
    ]
    if brief.project_id is not None or brief.project_name:
        lines.append(f"Проект: {brief.project_name or '(без имени)'} (id={brief.project_id})")
    if brief.business_type:
        lines.append(f"Бизнес-тип: {brief.business_type}")
    if brief.business_unit:
        lines.append(f"Бизнес-единица: {brief.business_unit}")
    if brief.business_goal_hint.strip():
        lines.append(f"Бизнес-цель: {brief.business_goal_hint.strip()[:500]}")
    if brief.related_task_id is not None:
        lines.append(f"Связанная миссия: #{brief.related_task_id}")
    if brief.context_summary.strip():
        lines.append("Контекст (резолвер):")
        lines.append(brief.context_summary.strip()[:4000])
    if brief.memory_refs:
        lines.append("Память (refs): " + ", ".join(brief.memory_refs[:20]))
    lines.extend(
        [
            f"Кратко вход: {brief.input_summary.strip() or '(пусто)'}",
            f"Ожидаемый результат: {brief.desired_outcome.strip() or '(не указан)'}",
        ]
    )
    if brief.constraints:
        lines.append("Ограничения:")
        for c in brief.constraints[:15]:
            lines.append(f"  - {c}")
    if brief.attachments:
        lines.append("Вложения (описания):")
        for a in brief.attachments:
            lines.append(f"  - [{a.kind}] {a.description[:500]}")
    if original_input.strip():
        lines.extend(["", "Исходный ввод:", original_input.strip()[:8000]])
    return "\n".join(lines)


def normalize_intake(
    req: NormalizeIntakeRequest,
    *,
    parent_message_text: str | None = None,
    repo: TaskRepository | None = None,
) -> NormalizeIntakeResponse:
    t0 = time.perf_counter()
    combined = _combined_user_text(req, [])
    combined_preview = combined[:200]
    for a in req.attachments:
        if a.description:
            combined_preview += f" | [{a.kind}] {a.description[:80]}"

    resp = classify_intake(req, parent_message_text=parent_message_text)
    if repo is not None and intake_v1_enabled():
        from app.intake.decision_engine import apply_intake_v1

        reply_tid = _resolve_reply_task_id(req, parent_message_text)
        resp = apply_intake_v1(
            resp,
            req,
            repo,
            combined_text=combined,
            reply_task_id=reply_tid,
        )

    if repo is not None:
        from app.owner_memory.service import owner_memory_enabled
        from app.owner_memory.rules_engine import apply_owner_layer_to_normalize_response

        if owner_memory_enabled():
            resp, owner_eng = apply_owner_layer_to_normalize_response(resp, repo)
            merged_keys = list(dict.fromkeys(owner_eng.item_keys_applied + owner_eng.soft_preferences[:12]))
            resp = resp.model_copy(
                update={
                    "owner_rule_keys_applied": merged_keys,
                    "owner_explanation": (owner_eng.reasoning_summary or "")[:2000],
                    "owner_hard_block_intake": bool(owner_eng.hard_blocks),
                }
            )

    from app.intake.business_intent import apply_business_intent

    resp = apply_business_intent(resp)

    from app.gm_director import apply_gm_layer

    resp = apply_gm_layer(resp)

    latency_ms = int((time.perf_counter() - t0) * 1000)

    gm = resp.gm_decision
    log_extra: dict = {
        "intent": resp.intent_type,
        "decision": resp.decision,
        "confidence": resp.confidence,
        "source": req.source,
        "latency_ms": latency_ms,
        "input_redacted": redact(combined_preview)[:500],
        "matched_project_id": resp.matched_project_id,
        "matched_task_id": resp.matched_task_id,
        "similarity_score": resp.similarity_score,
        "memory_used": resp.memory_used,
        "decision_reason": (resp.decision_reason or "")[:300],
        "owner_rule_keys": (resp.owner_rule_keys_applied or [])[:20],
        "owner_hard_block_intake": resp.owner_hard_block_intake,
    }
    if gm:
        log_extra.update(
            {
                "gm_decision": f"{gm.execution_mode}/{gm.action}",
                "execution_mode": gm.execution_mode,
                "risk_level": gm.risk_level,
                "agents_selected": gm.agents_plan,
                "reason": (gm.explanation or "")[:400],
            }
        )
    logger.info("smart_intake_normalize", extra=log_extra)
    return resp


def response_to_public_dict(resp: NormalizeIntakeResponse) -> dict[str, Any]:
    """Сериализация для JSON API."""
    return {
        "intent_type": resp.intent_type,
        "confidence": resp.confidence,
        "task_brief": resp.task_brief.model_dump(),
        "needs_clarification": resp.needs_clarification,
        "clarifying_questions": resp.clarifying_questions,
        "decision": resp.decision,
        "matched_project_id": resp.matched_project_id,
        "matched_task_id": resp.matched_task_id,
        "similarity_score": resp.similarity_score,
        "decision_reason": resp.decision_reason,
        "memory_used": resp.memory_used,
        "owner_rule_keys_applied": resp.owner_rule_keys_applied,
        "owner_explanation": resp.owner_explanation,
        "owner_hard_block_intake": resp.owner_hard_block_intake,
        "business_intent": resp.business_intent,
        "business_action": resp.business_action.model_dump() if resp.business_action else None,
        "gm_decision": resp.gm_decision.model_dump() if resp.gm_decision else None,
    }
