# app/orchestrator/triage.py — определить domain, criticality, plan_or_execute
from __future__ import annotations

import logging
import re

from app.config import get_routing, get_policy, get_orchestration_config
from app.orchestrator.crewai_bridge import crewai_strict_required, get_last_crewai_error, run_crewai_triage
from app.orchestrator.exploration import detect_exploration_intent
from app.orchestrator.marketing_intent import detect_marketing_plan_intent
from app.orchestrator.revenue_intent import detect_revenue_intent
from app.orchestrator.agent_clusters import attach_agent_cluster

logger = logging.getLogger(__name__)


def _finalize_triage(result: dict, *, log_tag: str = "") -> dict:
    out = attach_agent_cluster(result)
    tag = f" ({log_tag})" if log_tag else ""
    logger.info(
        "TRIAGE RESULT%s domain=%s task_type=%s agent_cluster=%s revenue_override=%s exploration_mode=%s",
        tag,
        out.get("domain"),
        out.get("task_type"),
        out.get("agent_cluster"),
        out.get("revenue_intent_override"),
        out.get("exploration_mode"),
    )
    return out

REVENUE_OVERRIDE_DOMAIN = "BUSINESS"
REVENUE_OVERRIDE_TASK_TYPE = "revenue_execution"
MARKETING_OVERRIDE_DOMAIN = "MEDIA_OPS"
MARKETING_OVERRIDE_TASK_TYPE = "marketing_plan"
VALID_CRITICALITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_EXECUTION_MODES = {"PLAN", "EXECUTE"}
CRITICALITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
PROJECT_ROUTE_HINTS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("snowpolia", "снегополия"), "GAME", "economy_balance"),
    (("sponsorship platform", "спонсорская платформа"), "SPONSOR_PLATFORM", "mvp_scoring"),
    (("extrememedia", "extreme media"), "RND_EXTREME", "judge_console_mvp"),
)

# Порядок важен: первое совпадение побеждает (специфичные фразы — выше общих «спонсор» / «event»).
DOMAIN_HINT_ORDERED: list[tuple[str, tuple[str, str]]] = [
    ("маркетингов", ("MEDIA_OPS", "marketing_plan")),
    ("marketing plan", ("MEDIA_OPS", "marketing_plan")),
    ("рекламный план", ("MEDIA_OPS", "marketing_plan")),
    ("рекламн", ("MEDIA_OPS", "marketing_plan")),
    ("маркетинг", ("MEDIA_OPS", "marketing_plan")),
    ("smm", ("MEDIA_OPS", "marketing_plan")),
    ("контент-план", ("MEDIA_OPS", "marketing_plan")),
    ("контент план", ("MEDIA_OPS", "marketing_plan")),
    ("стратегия запуска", ("EVENTS", "event_runbook")),
    ("стратегию запуска", ("EVENTS", "event_runbook")),
    ("план запуска", ("EVENTS", "event_runbook")),
    ("wakesafari", ("EVENTS", "event_runbook")),
    ("wake safari", ("EVENTS", "event_runbook")),
    ("запуск ивента", ("EVENTS", "event_runbook")),
    ("extreme media", ("RND_EXTREME", "judge_console_mvp")),
    ("снегополия", ("GAME", "economy_balance")),
    ("snowpolia", ("GAME", "economy_balance")),
    ("site", ("PRODUCT_DEV", "feature_delivery")),
    ("сайт", ("PRODUCT_DEV", "feature_delivery")),
    ("деплой", ("PRODUCT_DEV", "deploy_prod")),
    ("deploy", ("PRODUCT_DEV", "deploy_prod")),
    ("баг", ("PRODUCT_DEV", "software_bugfix")),
    ("bug", ("PRODUCT_DEV", "software_bugfix")),
    ("контент", ("MEDIA_OPS", "content_pipeline")),
    ("content", ("MEDIA_OPS", "content_pipeline")),
    ("новости", ("MEDIA_OPS", "content_pipeline")),
    ("news", ("MEDIA_OPS", "content_pipeline")),
    ("публикац", ("MEDIA_OPS", "publish_major")),
    ("publish", ("MEDIA_OPS", "publish_major")),
    ("ивент", ("EVENTS", "event_runbook")),
    ("event", ("EVENTS", "event_runbook")),
    ("соревнован", ("EVENTS", "judging_rules")),
    ("судь", ("EVENTS", "judging_rules")),
    ("ruza", ("RUZA", "general")),
    ("extreme", ("RND_EXTREME", "judge_console_mvp")),
    ("турьев", ("INFRA", "invest_model")),
    ("хутор", ("INFRA", "invest_model")),
    ("инвест", ("INFRA", "invest_model")),
    ("спонсор", ("SPONSOR_PLATFORM", "mvp_scoring")),
    ("книга", ("AUTHORITY_CONTENT", "book_outline")),
    ("методич", ("AUTHORITY_CONTENT", "book_outline")),
    ("бот", ("CLIENTOPS", "studio_bot_admin")),
    ("студия", ("CLIENTOPS", "studio_bot_admin")),
]


def validate_canonical_route(candidate: dict, routing: dict) -> list[str]:
    """Return semantic route errors without allowing LLM-owned identifiers."""
    errors: list[str] = []
    domains = routing.get("domains", {}) or {}
    domain = str(candidate.get("domain") or "").strip().upper()
    task_type = str(candidate.get("task_type") or "").strip()
    if domain not in domains:
        errors.append(f"unknown domain: {domain or '<empty>'}")
        return errors
    task_cfg = (domains.get(domain, {}).get("task_types") or {}).get(task_type)
    if not task_cfg:
        errors.append(f"unknown task_type for {domain}: {task_type or '<empty>'}")
    criticality = str(candidate.get("criticality") or "").strip().upper()
    if criticality and criticality not in VALID_CRITICALITIES:
        errors.append(f"invalid criticality: {criticality}")
    mode = str(candidate.get("plan_or_execute") or "").strip().upper()
    if mode and mode not in VALID_EXECUTION_MODES:
        errors.append(f"invalid plan_or_execute: {mode}")
    gate = str(candidate.get("execute_gate") or "").strip()
    if task_cfg and gate and gate != str(task_cfg.get("execute_gate") or ""):
        errors.append(f"non-canonical execute_gate: {gate}")
    return errors


def _triage_meta(result: dict, *, source: str, validation_status: str = "valid", validation_errors: list[str] | None = None) -> dict:
    result["triage_source"] = source
    result["triage_validation_status"] = validation_status
    if validation_errors:
        result["triage_validation_errors"] = list(validation_errors)
    else:
        result.pop("triage_validation_errors", None)
    return result


def _merge_crewai_triage(
    result: dict,
    crewai_result: dict,
    routing: dict,
    *,
    locked_keys: set[str] | None = None,
) -> dict:
    """Accept only CrewAI values that belong to the canonical routing contract."""
    merged = dict(result)
    locked = locked_keys or set()
    domains = routing.get("domains", {})

    candidate_domain = str(crewai_result.get("domain") or "").strip().upper()
    candidate_task_type = str(crewai_result.get("task_type") or "").strip()
    if "domain" not in locked and "task_type" not in locked and candidate_domain in domains:
        candidate_config = (domains[candidate_domain].get("task_types") or {}).get(candidate_task_type)
        if candidate_config:
            merged["domain"] = candidate_domain
            merged["task_type"] = candidate_task_type
            merged["criticality"] = candidate_config.get("criticality", merged.get("criticality"))
            merged["execute_gate"] = candidate_config.get("execute_gate", merged.get("execute_gate"))
    elif "task_type" not in locked:
        active_domain = str(merged.get("domain") or "")
        candidate_config = ((domains.get(active_domain) or {}).get("task_types") or {}).get(candidate_task_type)
        if candidate_config:
            merged["task_type"] = candidate_task_type
            merged["criticality"] = candidate_config.get("criticality", merged.get("criticality"))
            merged["execute_gate"] = candidate_config.get("execute_gate", merged.get("execute_gate"))

    criticality = str(crewai_result.get("criticality") or "").strip().upper()
    current_criticality = str(merged.get("criticality") or "MEDIUM").upper()
    if (
        "criticality" not in locked
        and criticality in VALID_CRITICALITIES
        and CRITICALITY_RANK[criticality] >= CRITICALITY_RANK.get(current_criticality, 1)
    ):
        merged["criticality"] = criticality

    execution_mode = str(crewai_result.get("plan_or_execute") or "").strip().upper()
    if (
        "plan_or_execute" not in locked
        and execution_mode in VALID_EXECUTION_MODES
        and not (merged.get("plan_or_execute") == "EXECUTE" and execution_mode == "PLAN")
    ):
        merged["plan_or_execute"] = execution_mode

    return merged


def _revenue_triage_result(owner_text: str, routing: dict) -> dict:
    domains_cfg = routing.get("domains", {})
    tt_cfg = (domains_cfg.get(REVENUE_OVERRIDE_DOMAIN) or {}).get("task_types", {})
    cfg = tt_cfg.get(REVENUE_OVERRIDE_TASK_TYPE, {})
    return {
        "domain": REVENUE_OVERRIDE_DOMAIN,
        "task_type": REVENUE_OVERRIDE_TASK_TYPE,
        "criticality": cfg.get("criticality", "HIGH"),
        "plan_or_execute": "EXECUTE",
        "execute_gate": cfg.get("execute_gate", "OWNER_APPROVAL_IF_PROD"),
        "revenue_intent_override": True,
        "marketing_plan_override": False,
    }


def _marketing_triage_result(owner_text: str, routing: dict) -> dict:
    domains_cfg = routing.get("domains", {})
    tt_cfg = (domains_cfg.get(MARKETING_OVERRIDE_DOMAIN) or {}).get("task_types", {})
    cfg = tt_cfg.get(MARKETING_OVERRIDE_TASK_TYPE, {})
    return {
        "domain": MARKETING_OVERRIDE_DOMAIN,
        "task_type": MARKETING_OVERRIDE_TASK_TYPE,
        "criticality": cfg.get("criticality", "MEDIUM"),
        "plan_or_execute": "PLAN",
        "execute_gate": cfg.get("execute_gate", "OWNER_APPROVAL_IF_PUBLISH"),
        "revenue_intent_override": False,
        "marketing_plan_override": True,
    }


def _explicit_task_triage(owner_text: str, routing: dict) -> dict | None:
    """Validated owner route takes precedence over inference and old snapshots."""
    text = (owner_text or "").lstrip()
    if not re.match(r"#\s*TASK\s+Domain\s*:", text, re.IGNORECASE):
        return None
    match = re.match(
        r"#\s*TASK\s+Domain\s*:\s*([A-Za-z_]+)\s*,\s*Type\s*:\s*([A-Za-z0-9_]+)\b",
        text, re.IGNORECASE,
    )
    if not match:
        raise ValueError("Malformed explicit #TASK route; specify Domain and Type.")
    domain, task_type = match.group(1).upper(), match.group(2).lower()
    config = (((routing.get("domains") or {}).get(domain) or {}).get("task_types") or {}).get(task_type)
    if not config:
        raise ValueError(f"Unknown explicit #TASK route: {domain}/{task_type}")
    execution_types = {"feature_delivery", "software_bugfix", "deploy_prod", "revenue_execution", "publish_major"}
    return {
        "domain": domain,
        "task_type": task_type,
        "criticality": config.get("criticality", "MEDIUM"),
        "plan_or_execute": "EXECUTE" if task_type in execution_types else "PLAN",
        "execute_gate": config.get("execute_gate", "OWNER_APPROVAL_IF_PROD"),
        "revenue_intent_override": False,
        "marketing_plan_override": False,
        "triage_source": "owner_explicit",
        "triage_validation_status": "valid",
        "triage_validation_errors": [],
    }


def _explicit_project_triage(owner_text: str, routing: dict) -> dict | None:
    """Return the canonical route when the owner names a known MyWave project."""
    text_lower = (owner_text or "").lower()
    domains = routing.get("domains", {})
    for aliases, domain, task_type in PROJECT_ROUTE_HINTS:
        if not any(alias in text_lower for alias in aliases):
            continue
        config = ((domains.get(domain) or {}).get("task_types") or {}).get(task_type, {})
        return {
            "domain": domain,
            "task_type": task_type,
            "criticality": config.get("criticality", "MEDIUM"),
            "plan_or_execute": "PLAN",
            "execute_gate": config.get("execute_gate", "OWNER_APPROVAL_IF_PROD"),
            "revenue_intent_override": False,
            "marketing_plan_override": False,
        }
    return None


def run_triage(owner_text: str) -> dict:
    """
    Rule-based triage. Возвращает:
    domain, task_type, criticality, plan_or_execute, execute_gate
    """
    raw_in = owner_text or ""
    logger.info(
        "triage_owner_text len=%s prefix=%r",
        len(raw_in),
        raw_in[:400] + ("…" if len(raw_in) > 400 else ""),
    )
    routing = get_routing()
    policy = get_policy()
    text_lower = (owner_text or "").lower()
    criticality_cfg = policy.get("criticality", {})
    execute_types = set(criticality_cfg.get("always_critical_if", []))

    explicit = _explicit_task_triage(owner_text, routing)
    if explicit:
        explicit["exploration_mode"] = detect_exploration_intent(owner_text)
        return _finalize_triage(explicit, log_tag="owner-explicit")

    # Explicit MyWave project names are a stronger signal than generic intent words.
    project_result = _explicit_project_triage(owner_text, routing)
    if project_result:
        project_result["exploration_mode"] = detect_exploration_intent(owner_text)
        orchestration_cfg = get_orchestration_config()
        crewai_result = run_crewai_triage(owner_text)
        if crewai_result:
            route_errors = validate_canonical_route(crewai_result, routing)
            if route_errors:
                if crewai_strict_required(orchestration_cfg):
                    raise RuntimeError("CrewAI triage semantic validation failed: " + "; ".join(route_errors))
                _triage_meta(project_result, source="fallback", validation_status="fallback", validation_errors=route_errors)
            else:
                _triage_meta(project_result, source="llm_normalized")
            if not route_errors:
                project_result = _merge_crewai_triage(
                    project_result,
                    crewai_result,
                    routing,
                    locked_keys={"domain", "task_type", "revenue_intent_override", "marketing_plan_override"},
                )
        elif crewai_strict_required(orchestration_cfg):
            detail = get_last_crewai_error() or "empty result"
            raise RuntimeError(f"CrewAI triage required but unavailable: {detail}")
        return _finalize_triage(project_result, log_tag="explicit-project")

    # Revenue-first: не даём DOMAIN_HINT (wakesafari → EVENTS) и CrewAI перебить коммерческий контур.
    if detect_revenue_intent(owner_text):
        result = _revenue_triage_result(owner_text, routing)
        result["exploration_mode"] = False
        orchestration_cfg = get_orchestration_config()
        crewai_result = run_crewai_triage(owner_text)
        if crewai_result:
            route_errors = validate_canonical_route(crewai_result, routing)
            if route_errors:
                if crewai_strict_required(orchestration_cfg):
                    raise RuntimeError("CrewAI triage semantic validation failed: " + "; ".join(route_errors))
                _triage_meta(result, source="fallback", validation_status="fallback", validation_errors=route_errors)
            else:
                _triage_meta(result, source="llm_normalized")
            if not route_errors:
                result = _merge_crewai_triage(
                    result,
                    crewai_result,
                    routing,
                    locked_keys={
                        "domain",
                        "task_type",
                        "revenue_intent_override",
                        "marketing_plan_override",
                        "plan_or_execute",
                    },
                )
        elif crewai_strict_required(orchestration_cfg):
            detail = get_last_crewai_error() or "empty result"
            raise RuntimeError(f"CrewAI triage required but unavailable: {detail}")
        return _finalize_triage(result, log_tag="revenue-first")

    # Marketing plan (zero-budget / рекламный план): не уводить в PRODUCT_DEV/feature_delivery.
    if detect_marketing_plan_intent(owner_text):
        result = _marketing_triage_result(owner_text, routing)
        result["exploration_mode"] = detect_exploration_intent(owner_text)
        orchestration_cfg = get_orchestration_config()
        crewai_result = run_crewai_triage(owner_text)
        if crewai_result:
            route_errors = validate_canonical_route(crewai_result, routing)
            if route_errors:
                if crewai_strict_required(orchestration_cfg):
                    raise RuntimeError("CrewAI triage semantic validation failed: " + "; ".join(route_errors))
                _triage_meta(result, source="fallback", validation_status="fallback", validation_errors=route_errors)
            else:
                _triage_meta(result, source="llm_normalized")
            if not route_errors:
                result = _merge_crewai_triage(
                    result,
                    crewai_result,
                    routing,
                    locked_keys={
                        "domain",
                        "task_type",
                        "revenue_intent_override",
                        "marketing_plan_override",
                        "plan_or_execute",
                    },
                )
        elif crewai_strict_required(orchestration_cfg):
            detail = get_last_crewai_error() or "empty result"
            raise RuntimeError(f"CrewAI triage required but unavailable: {detail}")
        return _finalize_triage(result, log_tag="marketing-plan")

    domain = "PRODUCT_DEV"
    task_type = "feature_delivery"
    execute_gate = "OWNER_APPROVAL_IF_PROD"

    for hint, (d, t) in DOMAIN_HINT_ORDERED:
        if hint in text_lower:
            domain = d
            task_type = t
            break

    # Получить execute_gate из routing
    domains_cfg = routing.get("domains", {})
    if domain in domains_cfg:
        task_types_cfg = domains_cfg[domain].get("task_types", {})
        if task_type in task_types_cfg:
            cfg = task_types_cfg[task_type]
            execute_gate = cfg.get("execute_gate", execute_gate)
            criticality = cfg.get("criticality", "MEDIUM")
        else:
            criticality = "MEDIUM"
    else:
        criticality = "MEDIUM"

    plan_or_execute = "PLAN"
    if any(
        ex in text_lower
        for ex in ["деплой", "deploy", "публикац", "publish", "деньги", "money", "договор", "contract"]
    ):
        plan_or_execute = "EXECUTE"
        if task_type in execute_types or criticality == "CRITICAL":
            criticality = "CRITICAL"

    result = {
        "domain": domain,
        "task_type": task_type,
        "criticality": criticality,
        "plan_or_execute": plan_or_execute,
        "execute_gate": execute_gate,
    }

    orchestration_cfg = get_orchestration_config()
    crewai_result = run_crewai_triage(owner_text)
    _triage_meta(result, source="rules")
    if crewai_result:
        route_errors = validate_canonical_route(crewai_result, routing)
        if route_errors:
            if crewai_strict_required(orchestration_cfg):
                raise RuntimeError("CrewAI triage semantic validation failed: " + "; ".join(route_errors))
            _triage_meta(result, source="fallback", validation_status="fallback", validation_errors=route_errors)
        else:
            _triage_meta(result, source="llm_normalized")
        if not route_errors:
            result = _merge_crewai_triage(result, crewai_result, routing)
    elif crewai_strict_required(orchestration_cfg):
        detail = get_last_crewai_error() or "empty result"
        raise RuntimeError(f"CrewAI triage required but unavailable: {detail}")

    result["revenue_intent_override"] = False
    result["marketing_plan_override"] = False
    result["exploration_mode"] = detect_exploration_intent(owner_text)
    return _finalize_triage(result)
