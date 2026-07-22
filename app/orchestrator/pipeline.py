# app/orchestrator/pipeline.py — config-driven шаги, Handoff
import os
from pathlib import Path

from app.config import get_routing, get_orchestration_config
from app.dashboard.documents import extract_document_text
from app.orchestrator.crewai_bridge import run_crewai_pipeline
from app.shared.redaction import redact


ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts"))

STEP_FOCUS = {
    "PM": "scope, sequencing, and owner acceptance criteria",
    "PS": "product framing and outcome definition",
    "UX": "user flow and surface expectations",
    "FE": "frontend implementation shape",
    "BE": "backend contract and data flow",
    "FE_BE": "implementation split between frontend and backend",
    "ARCH": "system constraints and interface boundaries",
    "QA": "verification plan and regression risks",
    "DEVOPS": "deploy path, rollback, and health checks",
    "CONTENT": "content structure and publication readiness",
    "BRAND": "tone, consistency, and public fit",
    "PROMPT": "prompt and content-generation shape",
    "RC": "reality check against scope and constraints",
    "RC2": "second-pass independent validation",
    "LEGAL": "policy, contract, and compliance exposure",
    "FIN": "budget, pricing, and business impact",
    "DATA": "metrics, evidence, and data dependencies",
    "EVENT": "runbook, logistics, and timeline",
    "ML_PROMPT": "model behavior, prompt shape, and evidence design",
    "SEC": "security review and risk containment",
}

# Role → sections of zero-budget marketing draft
_MARKETING_STEP_SECTIONS = {
    "CONTENT": ("content_calendar_30d", "Контент-план 30 дней (0 ₽)"),
    "BRAND": ("audience_offer", "ЦА и оффер"),
    "PS": ("funnel_cta", "Воронка и CTA"),
    "DATA": ("metrics", "Метрики 7/30 дней"),
    "FIN": ("channels", "Бесплатные каналы и экономика времени"),
    "PM": ("owner_tomorrow", "Действия владельца"),
}


def run_pipeline(task_id: int, triage_result: dict, repo, control=None) -> dict:
    """
    Выполняет pipeline из routing.yaml.
    Каждый шаг пишет Handoff (json + краткий md).
    """
    routing = get_routing()
    domain = triage_result.get("domain", "PRODUCT_DEV")
    task_type = triage_result.get("task_type", "feature_delivery")

    domains_cfg = routing.get("domains", {})
    pipeline_steps = []
    if domain in domains_cfg:
        task_types_cfg = domains_cfg[domain].get("task_types", {})
        if task_type in task_types_cfg:
            pipeline_steps = task_types_cfg[task_type].get("pipeline", ["PM", "ARCH"])

    if not pipeline_steps:
        pipeline_steps = ["PM", "ARCH"]

    task = repo.get_task(task_id)
    owner_text = redact((task.owner_text or "").strip()) if task else ""
    attachment_docs = _load_attachment_documents(task)
    attachment_names = [name for name, _ in attachment_docs]
    attachment_context = _attachment_short_labels(task)
    owner_brief = _owner_brief_orchestration(owner_text, attachment_names)
    attachment_blocks = _format_attachment_blocks(attachment_docs)
    rule_excerpts = _rule_fallback_excerpts(attachment_docs)
    orchestration_cfg = get_orchestration_config()
    if control:
        control.set_phase("pipeline", message="Подготавливаю pipeline шагов.", current_step="")
        control.check_cancelled()

    crewai_context = {
        "owner_text": owner_text,
        "owner_brief": owner_brief,
        "attachment_context": attachment_context,
        "attachment_blocks": attachment_blocks,
        "triage_result": triage_result,
    }
    try:
        crewai_payloads = run_crewai_pipeline(
            task_id,
            pipeline_steps,
            crewai_context,
            control=control,
        )
    except TypeError as exc:
        if "control" not in str(exc):
            raise
        crewai_payloads = run_crewai_pipeline(task_id, pipeline_steps, crewai_context)
    if not crewai_payloads and not orchestration_cfg.get("allow_fallback", True) and orchestration_cfg.get("engine") == "crewai":
        raise RuntimeError("CrewAI pipeline required but unavailable")

    handoffs = []
    previous_step = None
    for i, step_name in enumerate(pipeline_steps):
        if control:
            control.set_phase("pipeline", message=f"Готовлю handoff роли {step_name}.", current_step=step_name)
            control.check_cancelled()
        next_action = pipeline_steps[i + 1] if i + 1 < len(pipeline_steps) else "Roundtable"
        fallback_payload = _build_handoff_payload(
            step_name=step_name,
            task_id=task_id,
            triage_result=triage_result,
            owner_brief=owner_brief,
            attachment_context=attachment_context,
            attachment_rule_excerpts=rule_excerpts,
            next_action=next_action,
            previous_step=previous_step,
        )
        payload = _merge_payloads(
            fallback_payload,
            crewai_payloads[i] if i < len(crewai_payloads) else None,
            next_action,
        )
        md_content = redact(_handoff_to_md(step_name, payload))
        artifacts_path = ARTIFACTS_DIR / "handoffs"
        artifacts_path.mkdir(parents=True, exist_ok=True)
        md_path = artifacts_path / f"task_{task_id}_step_{i}.md"
        md_path.write_text(md_content, encoding="utf-8")

        repo.add_handoff(
            task_id=task_id,
            step_index=i,
            step_name=step_name,
            payload=payload,
            md_path=str(md_path),
        )
        handoffs.append({"step": step_name, "payload": payload, "md_path": str(md_path)})
        previous_step = step_name
        if control:
            control.check_cancelled()

    return {"handoffs": handoffs}


def _build_handoff_payload(
    step_name: str,
    task_id: int,
    triage_result: dict,
    owner_brief: str,
    attachment_context: list[str],
    attachment_rule_excerpts: list[str],
    next_action: str,
    previous_step: str | None,
) -> dict:
    domain = triage_result.get("domain", "PRODUCT_DEV")
    task_type = triage_result.get("task_type", "feature_delivery")
    criticality = triage_result.get("criticality", "MEDIUM")
    plan_or_execute = triage_result.get("plan_or_execute", "PLAN")
    execute_gate = triage_result.get("execute_gate", "OWNER_APPROVAL_IF_PROD")
    focus = STEP_FOCUS.get(step_name, "structured review for the next handoff")

    summary = [
        f"{step_name} prepared handoff for task #{task_id} ({domain}/{task_type}).",
        f"Primary focus: {focus}.",
        f"Owner brief: {owner_brief}",
    ]
    if attachment_context:
        summary.append(f"Owner files (short labels): {' | '.join(attachment_context)}")
    if attachment_rule_excerpts:
        summary.append(
            "Excerpts from owner-uploaded files (rule-based fallback; read these for substance when LLM is off):"
        )
        summary.extend(attachment_rule_excerpts)

    # Маркетинговый план за 0 ₽ — substantive draft в summary (не IT feature pack).
    if task_type == "marketing_plan" or triage_result.get("marketing_plan_override"):
        from app.orchestrator.marketing_intent import build_zero_budget_marketing_draft

        draft = build_zero_budget_marketing_draft(owner_brief)
        key_title = _MARKETING_STEP_SECTIONS.get(step_name)
        if key_title:
            section_key, title = key_title
            summary.append(f"=== {title} ===")
            summary.extend(draft.get(section_key, []))
        else:
            summary.append("=== Маркетинг (фрагмент) ===")
            summary.extend(draft.get("owner_tomorrow", [])[:3])
        # FIN also adds owner_tomorrow actions
        if step_name == "FIN":
            summary.append("=== Что сделать владельцу ===")
            summary.extend(draft.get("owner_tomorrow", []))

    decisions = [
        f"Keep task criticality at {criticality}.",
        f"Hand off to {next_action}.",
    ]
    if previous_step:
        decisions.insert(0, f"Use context carried from {previous_step}.")
    if task_type == "marketing_plan":
        decisions.append("Deliver a zero-budget marketing plan; do not route as software feature delivery.")

    assumptions = [
        f"Task is currently treated as {plan_or_execute}.",
        f"Execute gate is {execute_gate}.",
    ]
    if plan_or_execute == "EXECUTE":
        assumptions.append("Execution request is present in the owner brief and must stay gated.")
    if task_type == "marketing_plan":
        assumptions.append("Paid media budget is 0; only organic channels and partnerships.")

    risks = []
    if criticality in {"HIGH", "CRITICAL"}:
        risks.append(f"{criticality} criticality requires tighter verification before closure.")
    gate_lower = (execute_gate or "").lower()
    if task_type == "marketing_plan":
        risks.append("Organic reach is slow; owner must execute content cadence personally.")
        risks.append("Partner/barter deals need clear value exchange to avoid unpaid labor traps.")
    elif "prod" in gate_lower:
        risks.append("Production-facing path needs rollback and healthcheck confirmation.")
    if any(token in gate_lower for token in ("publish", "public")):
        risks.append("Public output must be reviewed before release.")
    if any(token in gate_lower for token in ("money", "contract", "legal")):
        risks.append("Commercial or legal impact needs explicit owner review.")
    if any(token in gate_lower for token in ("pii", "sensitive", "video")):
        risks.append("Sensitive data handling needs redaction and access control review.")

    open_questions = []
    if len(owner_brief) < 80 and not attachment_rule_excerpts:
        open_questions.append("Owner brief is short; confirm exact scope and acceptance criteria if execution expands.")
    if plan_or_execute == "EXECUTE" and "always" in gate_lower:
        open_questions.append("Confirm explicit owner approval window before any execute action.")
    if task_type == "marketing_plan":
        open_questions.append("Confirm city/geo and primary offer (trial vs membership) if not explicit in brief.")

    return {
        "summary": summary,
        "artifacts": [
            f"routing::{domain}/{task_type}",
            f"policy::{criticality}/{plan_or_execute}",
            f"handoff::{step_name.lower()}",
            *(["deliverable::zero_budget_marketing_plan"] if task_type == "marketing_plan" else []),
        ],
        "decisions": decisions,
        "assumptions": assumptions,
        "risks": risks,
        "open_questions": open_questions,
        "next_action": next_action,
    }


def _merge_payloads(fallback_payload: dict, crewai_payload: dict | None, next_action: str) -> dict:
    if not crewai_payload:
        return fallback_payload

    merged = {}
    for key, fallback_value in fallback_payload.items():
        if key == "next_action":
            merged[key] = crewai_payload.get(key) or next_action or fallback_value
            continue
        candidate = crewai_payload.get(key)
        merged[key] = candidate if candidate else fallback_value
    return merged


def _owner_brief_orchestration(owner_text: str, attachment_names: list[str]) -> str:
    cfg = get_orchestration_config()
    limit = int(cfg.get("owner_brief_limit", 12000))
    base = (owner_text or "").strip()
    if not base:
        base = "Owner brief not provided."
    if len(base) > limit:
        base = base[: limit - 3] + "..."
    if attachment_names:
        note = "\n\n[Вложения для анализа: " + ", ".join(attachment_names) + "]"
        if len(base) + len(note) <= limit + 500:
            base = base + note
        elif len(base) + len(note) > limit + 500:
            base = (base + note)[: limit + 497] + "..."
    return base


def _load_attachment_documents(task) -> list[tuple[str, str]]:
    """Полные тексты вложений с диска (с лимитами), для LLM и rule-based выдержек."""
    if not task:
        return []
    cfg = get_orchestration_config()
    per_file = int(cfg.get("attachment_max_per_file", 60000))
    max_total = int(cfg.get("attachment_max_total", 240000))
    out: list[tuple[str, str]] = []
    total = 0
    handoffs = sorted(
        [
            h
            for h in (getattr(task, "handoffs", []) or [])
            if (getattr(h, "payload_json", None) or {}).get("document_role") == "source_attachment"
        ],
        key=lambda h: (h.step_index, getattr(h, "id", 0)),
    )
    for handoff in handoffs:
        if total >= max_total:
            break
        path_str = handoff.md_path
        if not path_str:
            continue
        path = Path(path_str)
        if not path.is_file():
            continue
        try:
            raw = extract_document_text(path)
        except OSError:
            continue
        text = redact(raw)
        payload = handoff.payload_json or {}
        name = payload.get("original_name") or payload.get("document_title") or path.name
        room = min(per_file, max(0, max_total - total))
        if room <= 0:
            break
        if len(text) > room:
            text = text[: room - 1] + "…"
        out.append((name, text))
        total += len(text)
    return out


def _format_attachment_blocks(docs: list[tuple[str, str]]) -> str:
    if not docs:
        return ""
    parts = []
    for name, text in docs:
        parts.append(f"--- FILE: {name} ---\n{text}\n")
    return "\n".join(parts)


def _rule_fallback_excerpts(docs: list[tuple[str, str]]) -> list[str]:
    cfg = get_orchestration_config()
    per = int(cfg.get("rule_fallback_excerpt_per_file", 8000))
    lines = []
    for name, text in docs:
        chunk = text if len(text) <= per else text[: per - 1] + "…"
        lines.append(f"{name}: {chunk}")
    return lines


def _attachment_short_labels(task, limit: int = 12) -> list[str]:
    """Короткие подписи (имя + превью из payload) для сводок."""
    if not task:
        return []
    items = []
    for handoff in getattr(task, "handoffs", []) or []:
        payload = getattr(handoff, "payload_json", None) or {}
        if payload.get("document_role") != "source_attachment":
            continue
        name = payload.get("original_name") or payload.get("document_title") or Path(handoff.md_path or "").name
        preview = " ".join(str(payload.get("preview_excerpt", "")).split())
        if preview:
            items.append(f"{name}: {preview}")
        else:
            items.append(str(name))
        if len(items) >= limit:
            break
    return items


def _handoff_to_md(step_name: str, payload: dict) -> str:
    lines = [f"# Handoff: {step_name}", ""]
    for k, v in payload.items():
        if isinstance(v, list):
            lines.append(f"## {k}")
            for item in v:
                lines.append(f"- {item}")
        else:
            lines.append(f"## {k}\n{v}")
        lines.append("")
    return "\n".join(lines)
