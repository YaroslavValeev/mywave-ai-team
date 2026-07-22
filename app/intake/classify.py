# Rule-based + опциональный LLM fallback для Smart Intake v0
from __future__ import annotations

import json
import logging
import os
import re
from app.intake.schemas import (
    NormalizeIntakeRequest,
    NormalizeIntakeResponse,
    TaskBrief,
)

logger = logging.getLogger(__name__)

NOISE_EXACT = frozenset(
    {
        "ок",
        "ок.",
        "ok",
        "ok.",
        "спасибо",
        "thanks",
        "thx",
        "спс",
        "да",
        "нет",
        "hi",
        "hello",
        "привет",
        "👍",
        "👌",
    }
)

ACTION_RE = re.compile(
    r"\b(нужно|надо|сделать|сделай|исправить|исправь|добавить|добавь|проверить|проверь|"
    r"реализовать|внедрить|убрать|починить|fix|add|implement|deploy|ошибк|error|bug|api|ключ)\b",
    re.IGNORECASE,
)

TASK_ID_IN_TEXT_RE = re.compile(
    r"(?:миссия|mission|task)\s*#?\s*(\d+)|#(\d+)\b(?:\s|$)|task[_\s]?id\s*[=:]?\s*(\d+)",
    re.IGNORECASE,
)


def parse_task_id_from_text(text: str | None) -> int | None:
    if not text:
        return None
    m = TASK_ID_IN_TEXT_RE.search(text)
    if not m:
        return None
    for g in m.groups():
        if g:
            try:
                return int(g)
            except ValueError:
                continue
    return None


def _combined_user_text(req: NormalizeIntakeRequest, extra_lines: list[str]) -> str:
    parts = [req.text.strip()]
    for a in req.attachments:
        if a.description.strip():
            parts.append(a.description.strip())
    parts.extend(extra_lines)
    return "\n\n".join(p for p in parts if p).strip()


def _resolve_reply_task_id(req: NormalizeIntakeRequest, parent_text: str | None) -> int | None:
    tid = req.reply_task_id()
    if tid is not None:
        return tid
    raw = req.reply_context
    if isinstance(raw, dict):
        pt = raw.get("parent_text") or (raw.get("raw") or {}).get("parent_text")
        if isinstance(pt, str):
            return parse_task_id_from_text(pt) or tid
    if parent_text:
        return parse_task_id_from_text(parent_text)
    return None


def rule_based_classify(req: NormalizeIntakeRequest, combined: str, reply_task_id: int | None) -> NormalizeIntakeResponse:
    low = combined.lower().strip()
    words = low.split()

    if not low:
        return NormalizeIntakeResponse(
            intent_type="noise",
            confidence=0.99,
            task_brief=TaskBrief(input_summary="(пустой ввод)"),
            needs_clarification=False,
            clarifying_questions=[],
            decision="reject",
        )

    if len(low) <= 24 and low in NOISE_EXACT:
        return NormalizeIntakeResponse(
            intent_type="noise",
            confidence=0.95,
            task_brief=TaskBrief(title="Шум", input_summary=combined[:500]),
            needs_clarification=False,
            clarifying_questions=[],
            decision="reject",
        )

    if reply_task_id is not None and len(combined) >= 8:
        brief = TaskBrief(
            title=f"Дополнение к задаче #{reply_task_id}",
            goal="Расширить контекст существующей миссии",
            input_summary=combined[:2000],
            desired_outcome="Учесть дополнение при следующем прогоне",
            attachments=list(req.attachments),
            requires_owner_approval=True,
        )
        return NormalizeIntakeResponse(
            intent_type="task",
            confidence=0.78,
            task_brief=brief,
            needs_clarification=False,
            clarifying_questions=[],
            decision="attach",
        )

    if "?" in combined and len(words) <= 35 and not ACTION_RE.search(combined):
        qs = [
            "Это запрос на новую работу (нужен артефакт/изменение в коде) или только вопрос?",
            "Если нужна задача — кратко опишите желаемый результат одним предложением.",
        ]
        brief = TaskBrief(
            title="Уточнение намерения",
            goal="Понять, создавать ли задачу",
            input_summary=combined[:2000],
            desired_outcome="Ясное ТЗ",
            attachments=list(req.attachments),
            requires_owner_approval=True,
        )
        return NormalizeIntakeResponse(
            intent_type="question",
            confidence=0.62,
            task_brief=brief,
            needs_clarification=True,
            clarifying_questions=qs[:3],
            decision="clarify",
        )

    # default: создать задачу
    title = (combined[:80] + "…") if len(combined) > 80 else combined
    brief = TaskBrief(
        title=title.replace("\n", " "),
        goal="Выполнить запрос владельца",
        input_summary=combined[:4000],
        desired_outcome="Готовый план/артефакты по контуру AI Office",
        constraints=[],
        attachments=list(req.attachments),
        requires_owner_approval=True,
    )
    conf = 0.72 if ACTION_RE.search(combined) else 0.55
    return NormalizeIntakeResponse(
        intent_type="task",
        confidence=min(0.95, conf + 0.1 * min(len(words) / 40, 1.0)),
        task_brief=brief,
        needs_clarification=False,
        clarifying_questions=[],
        decision="create",
    )


def llm_classify(combined: str, req: NormalizeIntakeRequest) -> NormalizeIntakeResponse | None:
    if os.getenv("INTAKE_USE_LLM", "").strip().lower() not in {"1", "true", "yes"}:
        return None
    key = (os.getenv("OPENAI_API_KEY") or os.getenv("CREWAI_API_KEY") or "").strip()
    if not key:
        return None
    model = os.getenv("INTAKE_LLM_MODEL", "gpt-4o-mini")
    try:
        import httpx
    except ImportError:
        logger.warning("httpx missing for INTAKE_USE_LLM")
        return None

    prompt = f"""Classify owner message for an internal task system. Return JSON only with keys:
intent_type (task|question|analysis|clarify|noise),
confidence (0-1),
decision (create|clarify|attach|reject),
needs_clarification (bool),
clarifying_questions (array of strings, max 3),
task_brief: {{
  title, goal, input_summary, desired_outcome, constraints (array of strings),
  requires_owner_approval (bool)
}}
Source: {req.source}. User message:
---
{combined[:8000]}
---

If message is trivial ack (ok, thanks) use noise/reject.
If user asks a pure question without requesting work, use question/clarify."""

    try:
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=60.0,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        tb = parsed.get("task_brief") or {}
        brief = TaskBrief(
            title=str(tb.get("title") or "")[:500],
            goal=str(tb.get("goal") or "")[:2000],
            input_summary=str(tb.get("input_summary") or combined[:4000])[:4000],
            desired_outcome=str(tb.get("desired_outcome") or "")[:2000],
            constraints=[str(x) for x in (tb.get("constraints") or []) if x][:20],
            attachments=list(req.attachments),
            requires_owner_approval=bool(tb.get("requires_owner_approval", True)),
        )
        it = parsed.get("intent_type") or "task"
        if it not in ("task", "question", "analysis", "clarify", "noise"):
            it = "task"
        dec = parsed.get("decision") or "create"
        if dec not in ("create", "clarify", "attach", "reject"):
            dec = "create"
        cf = float(parsed.get("confidence") or 0.7)
        cf = max(0.0, min(1.0, cf))
        qs = [str(x) for x in (parsed.get("clarifying_questions") or [])][:3]
        return NormalizeIntakeResponse(
            intent_type=it,  # type: ignore[arg-type]
            confidence=cf,
            task_brief=brief,
            needs_clarification=bool(parsed.get("needs_clarification")),
            clarifying_questions=qs,
            decision=dec,  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.warning("INTAKE LLM failed: %s", exc)
        return None


def classify_intake(
    req: NormalizeIntakeRequest,
    *,
    parent_message_text: str | None = None,
) -> NormalizeIntakeResponse:
    """Правила + опционально LLM поверх объединённого текста."""
    reply_tid = _resolve_reply_task_id(req, parent_message_text)
    combined = _combined_user_text(req, [])

    llm_out = llm_classify(combined, req)
    if llm_out is not None:
        low = combined.lower().strip()
        if reply_tid is not None and len(combined) >= 8:
            if llm_out.decision == "reject" and low in NOISE_EXACT:
                return llm_out
            rb = llm_out.task_brief
            brief = TaskBrief(
                title=rb.title.strip() or f"Дополнение к задаче #{reply_tid}",
                goal=rb.goal.strip() or "Дополнить контекст миссии",
                input_summary=combined[:4000],
                desired_outcome=rb.desired_outcome.strip() or "Учесть дополнение при следующем прогоне",
                constraints=rb.constraints,
                attachments=list(req.attachments),
                requires_owner_approval=True,
            )
            return NormalizeIntakeResponse(
                intent_type="task",
                confidence=max(llm_out.confidence, 0.78),
                task_brief=brief,
                needs_clarification=False,
                clarifying_questions=[],
                decision="attach",
            )
        return llm_out

    return rule_based_classify(req, combined, reply_tid)
