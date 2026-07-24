# app/orchestrator/crewai_bridge.py — optional CrewAI bridge with safe fallback
import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.config import get_orchestration_config

logger = logging.getLogger(__name__)

TRIAGE_KEYS = {"domain", "task_type", "criticality", "plan_or_execute", "execute_gate"}
PAYLOAD_KEYS = {"summary", "artifacts", "decisions", "assumptions", "risks", "open_questions", "next_action"}

# Last CrewAI failure detail for strict-mode error messages (Telegram / audit).
_last_crewai_error: str = ""


def get_last_crewai_error() -> str:
    return _last_crewai_error


def _set_last_crewai_error(message: str) -> None:
    global _last_crewai_error
    _last_crewai_error = (message or "").strip()[:500]


def _strict_unavailable(kind: str) -> RuntimeError:
    detail = get_last_crewai_error() or "empty result (see app logs for CrewAI bridge)"
    return RuntimeError(f"CrewAI {kind} required but unavailable: {detail}")

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


def has_llm_credentials() -> bool:
    """True if local or cloud tier (or legacy env) can reach an LLM endpoint."""
    from app.orchestrator.llm_tier import tier_credentials_ok

    if tier_credentials_ok("local") or tier_credentials_ok("cloud"):
        return True
    if (os.getenv("OPENAI_API_KEY") or os.getenv("CREWAI_API_KEY") or "").strip():
        return True
    if (os.getenv("OPENAI_BASE_URL") or os.getenv("CREWAI_BASE_URL") or "").strip():
        return True
    return False


def crewai_strict_required(cfg: dict | None = None) -> bool:
    """True when rule-based fallback is forbidden (ALLOW_FALLBACK=false) for crewai|auto."""
    orchestration = cfg or get_orchestration_config()
    if orchestration.get("allow_fallback", True):
        return False
    return orchestration.get("engine", "auto") in ("crewai", "auto")


def is_crewai_enabled() -> bool:
    """
    CrewAI path is on for engine=crewai|auto.
    In auto mode without credentials — skip CrewAI (fast safe fallback to rule-based),
    unless allow_fallback=false (strict: still attempt / callers raise on empty result).
    Strict engine=crewai always returns True so callers can enforce allow_fallback policy.
    """
    cfg = get_orchestration_config()
    mode = cfg.get("engine", "auto")
    if mode == "crewai":
        return True
    if mode != "auto":
        return False
    if crewai_strict_required(cfg):
        return True
    return has_llm_credentials()


def run_crewai_triage(text: str) -> dict:
    """Try CrewAI triage. Return {} on unavailable/failure so caller can fallback.

    In strict mode (allow_fallback=false) raises RuntimeError with last failure detail.
    """
    if not is_crewai_enabled():
        _set_last_crewai_error("CrewAI path disabled (engine/credentials)")
        if crewai_strict_required():
            raise _strict_unavailable("triage")
        return {}

    description = (
        "Classify the owner task into JSON with keys "
        "`domain`, `task_type`, `criticality`, `plan_or_execute`, `execute_gate`.\n"
        "Allowed criticality: LOW, MEDIUM, HIGH, CRITICAL.\n"
        "Allowed plan_or_execute: PLAN or EXECUTE.\n"
        "Return JSON only, no markdown.\n\n"
        f"Owner task:\n{text or ''}"
    )
    result = _run_json_task(
        role="AGM Triage Analyst",
        goal="Route owner tasks into the correct domain and execution mode.",
        backstory="You classify MyWave tasks for a multi-agent operating system.",
        description=description,
        allowed_keys=TRIAGE_KEYS,
    )
    if result and not str(result.get("domain") or "").strip():
        _set_last_crewai_error("CrewAI triage returned empty domain")
        result = {}
    if not result and crewai_strict_required():
        raise _strict_unavailable("triage")
    return result


def run_crewai_pipeline(task_id: int, steps: list[str], context: dict, control=None) -> list[dict]:
    """Try CrewAI pipeline. Return [] on unavailable/failure so caller can fallback.

    In strict mode (allow_fallback=false) raises RuntimeError with last failure detail.
    """
    if not is_crewai_enabled() or not steps:
        if not steps:
            _set_last_crewai_error("empty pipeline steps")
        else:
            _set_last_crewai_error("CrewAI path disabled (engine/credentials)")
        if crewai_strict_required():
            raise _strict_unavailable("pipeline")
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
            _set_last_crewai_error(f"empty payload for step {step}: {get_last_crewai_error() or 'unknown'}")
            if crewai_strict_required():
                raise _strict_unavailable("pipeline")
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
    if llm is None:
        _set_last_crewai_error("LLM not configured (CREWAI_MODEL / OPENAI_API_KEY / OPENAI_BASE_URL)")
        logger.warning("CrewAI LLM missing for role %s", role)
        return {}

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
        timeout = int(get_orchestration_config().get("crewai_timeout", 120) or 120)
        result = _crew_kickoff(crew, timeout_sec=timeout)
        raw = _extract_task_output(task, result)
        parsed = _safe_json_loads(raw)
        if not isinstance(parsed, dict):
            snippet = (raw or "")[:300]
            _set_last_crewai_error(f"non-dict LLM output: {snippet or '(empty)'}")
            logger.warning("CrewAI returned non-dict output: %s", snippet)
            return {}
        normalized = _normalize_payload(parsed, allowed_keys)
        _set_last_crewai_error("")
        return normalized
    except Exception as exc:
        _set_last_crewai_error(f"{type(exc).__name__}: {exc}")
        logger.warning("CrewAI bridge failed for role %s: %s", role, exc)
        return {}


def _crew_kickoff(crew: Any, timeout_sec: int = 120) -> Any:
    """Run crew.kickoff() safely from sync and from a running asyncio loop (Telegram).

    CrewAI sync kickoff refuses to run when an event loop is already running
    (Telegram handlers call orchestration via asyncio.create_task). Offload to a
    worker thread in that case.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return crew.kickoff()

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="crewai-kickoff") as pool:
        return pool.submit(crew.kickoff).result(timeout=max(1, int(timeout_sec)))


def _load_crewai_classes() -> dict[str, Any] | None:
    try:
        from crewai import Agent, Task, Crew, Process, LLM  # type: ignore
    except Exception as exc:
        _set_last_crewai_error(f"import failed: {exc}")
        logger.info("CrewAI unavailable, fallback to rule-based orchestration: %s", exc)
        return None
    return {"Agent": Agent, "Task": Task, "Crew": Crew, "Process": Process, "LLM": LLM}


def _build_llm(classes: dict[str, Any]) -> Any | None:
    from app.orchestrator.llm_tier import describe_active_endpoint, endpoint_for_tier

    cfg = get_orchestration_config()
    ep = endpoint_for_tier()
    model = (ep.get("model") or "").strip()
    if not model and ep.get("api_key"):
        model = (os.getenv("CREWAI_DEFAULT_MODEL") or "gpt-4o-mini").strip()
    model = _normalize_model_name(model, ep.get("provider") or cfg.get("crewai_provider") or "")
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

    base_url = (ep.get("base_url") or "").strip()
    api_key = (ep.get("api_key") or "").strip()
    if base_url:
        # Ollama often listens without /v1; OpenAI-compatible clients expect it.
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        kwargs["base_url"] = base_url
        if not api_key:
            api_key = "local"
    if api_key:
        kwargs["api_key"] = api_key

    logger.info("CrewAI LLM endpoint: %s", describe_active_endpoint())
    try:
        return classes["LLM"](**kwargs)
    except Exception as exc:
        _set_last_crewai_error(f"LLM build failed for {model}: {exc}")
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
        # Triage fields are scalars (domain, task_type, …), not list handoffs.
        if key in TRIAGE_KEYS:
            if isinstance(value, list):
                value = value[0] if value else ""
            normalized[key] = str(value or "").strip()
            continue
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

    if os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL") or os.getenv("CREWAI_BASE_URL"):
        return f"openai/{candidate}"
    return candidate
