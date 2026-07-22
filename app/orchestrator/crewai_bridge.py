# app/orchestrator/crewai_bridge.py — optional CrewAI bridge with safe fallback
import json
import logging
import os
from typing import Any

from app.config import get_orchestration_config

logger = logging.getLogger(__name__)

TRIAGE_KEYS = {"domain", "task_type", "criticality", "plan_or_execute", "execute_gate"}
PAYLOAD_KEYS = {"summary", "artifacts", "decisions", "assumptions", "risks", "open_questions", "next_action"}

STEP_PROFILES = {
    "PM": {
        "role": "Delivery PM",
        "goal": "Turn the owner request into a scoped next-step plan.",
        "backstory": "You prepare compact execution-ready handoffs for the next role.",
    },
    "PS": {
        "role": "Product Strategist",
        "goal": "Clarify business outcome, scope, and success signal.",
        "backstory": "You frame ambiguous tasks into product decisions with minimal fluff.",
    },
    "UX": {
        "role": "UX Designer",
        "goal": "Describe the user flow and interface expectations.",
        "backstory": "You reduce ambiguity in user interactions and acceptance criteria.",
    },
    "FE": {
        "role": "Frontend Engineer",
        "goal": "Translate the task into frontend implementation concerns.",
        "backstory": "You focus on screens, states, validation, and UI risks.",
    },
    "BE": {
        "role": "Backend Engineer",
        "goal": "Translate the task into data, API, and backend concerns.",
        "backstory": "You focus on contracts, persistence, and operational correctness.",
    },
    "FE_BE": {
        "role": "Fullstack Engineer",
        "goal": "Split the task into frontend and backend work.",
        "backstory": "You produce compact handoffs that cover both UI and server impact.",
    },
    "ARCH": {
        "role": "Solution Architect",
        "goal": "Confirm boundaries, constraints, and interfaces.",
        "backstory": "You keep the implementation aligned with the current architecture.",
    },
    "QA": {
        "role": "QA Reviewer",
        "goal": "Build a verification plan and highlight regression risk.",
        "backstory": "You think in acceptance criteria, failure modes, and test evidence.",
    },
    "DEVOPS": {
        "role": "DevOps Engineer",
        "goal": "Prepare deploy, rollback, and healthcheck expectations.",
        "backstory": "You focus on safe rollout and operational reversibility.",
    },
    "CONTENT": {
        "role": "Content Operator",
        "goal": "Shape the task into content artifacts and publishing readiness.",
        "backstory": "You balance production speed with publication quality.",
    },
    "BRAND": {
        "role": "Brand Reviewer",
        "goal": "Protect tone, consistency, and public fit.",
        "backstory": "You focus on clarity, brand consistency, and external perception.",
    },
    "RC": {
        "role": "Reality Checker",
        "goal": "Challenge weak assumptions and spot missing evidence.",
        "backstory": "You are skeptical and concise, not destructive.",
    },
    "RC2": {
        "role": "Independent Reviewer",
        "goal": "Provide a second-pass validation of the proposed approach.",
        "backstory": "You act as a clean-room reviewer to surface blind spots.",
    },
    "LEGAL": {
        "role": "Legal Reviewer",
        "goal": "Highlight policy, contract, and public commitment risk.",
        "backstory": "You focus on commitments, liabilities, and wording risk.",
    },
    "FIN": {
        "role": "Finance Reviewer",
        "goal": "Surface pricing, budget, and commercial exposure.",
        "backstory": "You think in downside, commitments, and financial clarity.",
    },
    "DATA": {
        "role": "Data Analyst",
        "goal": "Identify evidence, metrics, and missing inputs.",
        "backstory": "You turn vague assertions into measurable requirements.",
    },
    "EVENT": {
        "role": "Event Operator",
        "goal": "Translate the task into a concrete operational runbook.",
        "backstory": "You focus on logistics, coordination, and timing.",
    },
    "ML_PROMPT": {
        "role": "ML Prompt Engineer",
        "goal": "Define model behavior, prompt constraints, and evidence expectations.",
        "backstory": "You turn experimentation into repeatable structured outputs.",
    },
    "SEC": {
        "role": "Security Reviewer",
        "goal": "Surface access, exposure, and misuse risks.",
        "backstory": "You enforce least surprise and least privilege.",
    },
}


def is_crewai_enabled() -> bool:
    mode = get_orchestration_config().get("engine", "auto")
    return mode in {"crewai", "auto"}


def run_crewai_triage(text: str) -> dict:
    """Try CrewAI triage. Return {} on unavailable/failure so caller can fallback."""
    if not is_crewai_enabled():
        return {}

    description = (
        "Classify the owner task into JSON with keys "
        "`domain`, `task_type`, `criticality`, `plan_or_execute`, `execute_gate`.\n"
        "Allowed criticality: LOW, MEDIUM, HIGH, CRITICAL.\n"
        "Allowed plan_or_execute: PLAN or EXECUTE.\n"
        "Return JSON only, no markdown.\n\n"
        f"Owner task:\n{text or ''}"
    )
    return _run_json_task(
        role="AGM Triage Analyst",
        goal="Route owner tasks into the correct domain and execution mode.",
        backstory="You classify MyWave tasks for a multi-agent operating system.",
        description=description,
        allowed_keys=TRIAGE_KEYS,
    )


def run_crewai_pipeline(task_id: int, steps: list[str], context: dict, control=None) -> list[dict]:
    """Try CrewAI pipeline. Return [] on unavailable/failure so caller can fallback."""
    if not is_crewai_enabled() or not steps:
        return []

    task_text = context.get("owner_text", "")
    triage = context.get("triage_result", {})
    owner_brief = context.get("owner_brief", "")
    attachment_blocks = (context.get("attachment_blocks") or "").strip()
    outputs = []
    prior_summary = "No prior handoffs."

    for index, step in enumerate(steps):
        if control:
            control.set_phase("pipeline", message=f"Локальная модель готовит шаг {step}.", current_step=step)
            control.check_cancelled()
        profile = STEP_PROFILES.get(
            step,
            {
                "role": f"{step} Specialist",
                "goal": "Produce a compact structured handoff for the next stage.",
                "backstory": "You work inside the MyWave AGM workflow and keep outputs structured.",
            },
        )
        next_action = steps[index + 1] if index + 1 < len(steps) else "Roundtable"
        files_section = (
            f"\n\n--- Owner-uploaded files (full text, respect for analysis) ---\n{attachment_blocks}\n"
            if attachment_blocks
            else ""
        )
        description = (
            "Produce JSON only with keys "
            "`summary`, `artifacts`, `decisions`, `assumptions`, `risks`, `open_questions`, `next_action`.\n"
            "All keys except `next_action` must contain arrays of short strings.\n"
            "Base your analysis on the owner instructions AND any attached files below.\n"
            f"Task id: {task_id}\n"
            f"Step: {step}\n"
            f"Next action: {next_action}\n"
            f"Triage: {json.dumps(triage, ensure_ascii=False)}\n"
            f"Owner brief (full): {owner_brief}\n"
            f"Raw owner task: {task_text}\n"
            f"Prior handoff summary: {prior_summary}\n"
            f"{files_section}"
            "Return JSON only."
        )
        payload = _run_json_task(
            role=profile["role"],
            goal=profile["goal"],
            backstory=profile["backstory"],
            description=description,
            allowed_keys=PAYLOAD_KEYS,
        )
        if not payload:
            logger.warning("CrewAI pipeline returned empty payload for step %s", step)
            return []
        payload["next_action"] = payload.get("next_action") or next_action
        outputs.append(payload)
        prior_summary = "; ".join(payload.get("summary", [])[:3]) or f"{step} completed"
        if control:
            control.check_cancelled()
    return outputs


def _run_json_task(
    *,
    role: str,
    goal: str,
    backstory: str,
    description: str,
    allowed_keys: set[str],
) -> dict:
    classes = _load_crewai_classes()
    if not classes:
        return {}

    Agent = classes["Agent"]
    Task = classes["Task"]
    Crew = classes["Crew"]
    Process = classes["Process"]
    llm = _build_llm(classes)

    try:
        agent = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            verbose=False,
            allow_delegation=False,
            llm=llm,
        )
        task = Task(
            description=description,
            expected_output="Strict JSON matching the requested keys.",
            agent=agent,
        )
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        raw = _extract_task_output(task, result)
        parsed = _safe_json_loads(raw)
        if not isinstance(parsed, dict):
            logger.warning("CrewAI returned non-dict output: %s", raw[:300])
            return {}
        return _normalize_payload(parsed, allowed_keys)
    except Exception as exc:
        logger.warning("CrewAI bridge failed for role %s: %s", role, exc)
        return {}


def _load_crewai_classes() -> dict[str, Any] | None:
    try:
        from crewai import Agent, Task, Crew, Process, LLM  # type: ignore
    except Exception as exc:
        logger.info("CrewAI unavailable, fallback to rule-based orchestration: %s", exc)
        return None
    return {"Agent": Agent, "Task": Task, "Crew": Crew, "Process": Process, "LLM": LLM}


def _build_llm(classes: dict[str, Any]) -> Any | None:
    cfg = get_orchestration_config()
    model = cfg.get("crewai_model") or os.getenv("OPENAI_MODEL_NAME") or os.getenv("MODEL") or ""
    model = (model or "").strip()
    if not model and (os.getenv("OPENAI_API_KEY") or os.getenv("CREWAI_API_KEY")):
        # Чтобы роли STEP_PROFILES реально вызывались при заданном ключе, без отдельного CREWAI_MODEL.
        model = (os.getenv("CREWAI_DEFAULT_MODEL") or "gpt-4o-mini").strip()
    model = _normalize_model_name(model, cfg.get("crewai_provider") or "")
    if not model:
        return None

    kwargs = {
        "model": model,
        "temperature": cfg.get("crewai_temperature", 0.2),
        "timeout": cfg.get("crewai_timeout", 120),
        "max_tokens": cfg.get("crewai_max_tokens", 2000),
    }
    if cfg.get("crewai_use_responses_api"):
        kwargs["response_format"] = {"type": "json_object"}

    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("CREWAI_BASE_URL") or ""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CREWAI_API_KEY") or ""
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key

    try:
        return classes["LLM"](**kwargs)
    except Exception as exc:
        logger.warning("Failed to build CrewAI LLM for model %s: %s", model, exc)
        return None


def _extract_task_output(task: Any, result: Any) -> str:
    output = getattr(task, "output", None)
    if output is not None:
        raw = getattr(output, "raw", None)
        if raw:
            return str(raw)
    return str(result or "")


def _safe_json_loads(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def _normalize_payload(payload: dict, allowed_keys: set[str]) -> dict:
    normalized = {}
    for key in allowed_keys:
        value = payload.get(key)
        if key == "next_action":
            normalized[key] = str(value or "").strip()
            continue
        if isinstance(value, list):
            normalized[key] = [str(item).strip() for item in value if str(item).strip()]
        elif value is None:
            normalized[key] = []
        else:
            text = str(value).strip()
            normalized[key] = [text] if text else []
    return normalized


def _normalize_model_name(model: str, provider: str) -> str:
    candidate = (model or "").strip()
    if not candidate:
        return ""
    if "/" in candidate:
        return candidate

    explicit_provider = (provider or "").strip()
    if explicit_provider:
        return f"{explicit_provider}/{candidate}"

    if os.getenv("OPENAI_API_KEY"):
        return f"openai/{candidate}"
    return candidate
