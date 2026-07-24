# app/orchestrator/triage.py — определить domain, criticality, plan_or_execute
from __future__ import annotations

import logging

from app.config import get_routing, get_policy, get_orchestration_config
from app.orchestrator.crewai_bridge import crewai_strict_required, run_crewai_triage
from app.orchestrator.exploration import detect_exploration_intent
from app.orchestrator.marketing_intent import detect_marketing_plan_intent
from app.orchestrator.revenue_intent import detect_revenue_intent

logger = logging.getLogger(__name__)

REVENUE_OVERRIDE_DOMAIN = "BUSINESS"
REVENUE_OVERRIDE_TASK_TYPE = "revenue_execution"
MARKETING_OVERRIDE_DOMAIN = "MEDIA_OPS"
MARKETING_OVERRIDE_TASK_TYPE = "marketing_plan"

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

    # Revenue-first: не даём DOMAIN_HINT (wakesafari → EVENTS) и CrewAI перебить коммерческий контур.
    if detect_revenue_intent(owner_text):
        result = _revenue_triage_result(owner_text, routing)
        result["exploration_mode"] = False
        orchestration_cfg = get_orchestration_config()
        crewai_result = run_crewai_triage(owner_text)
        if crewai_result:
            for key in result.keys():
                if key in {
                    "domain",
                    "task_type",
                    "revenue_intent_override",
                    "marketing_plan_override",
                    "plan_or_execute",
                }:
                    continue
                value = crewai_result.get(key)
                if value:
                    result[key] = value
        elif crewai_strict_required(orchestration_cfg):
            raise RuntimeError("CrewAI triage required but unavailable")
        logger.info(
            "TRIAGE RESULT (revenue-first) domain=%s task_type=%s revenue_override=%s",
            result.get("domain"),
            result.get("task_type"),
            result.get("revenue_intent_override"),
        )
        return result

    # Marketing plan (zero-budget / рекламный план): не уводить в PRODUCT_DEV/feature_delivery.
    if detect_marketing_plan_intent(owner_text):
        result = _marketing_triage_result(owner_text, routing)
        result["exploration_mode"] = detect_exploration_intent(owner_text)
        orchestration_cfg = get_orchestration_config()
        crewai_result = run_crewai_triage(owner_text)
        if crewai_result:
            for key in result.keys():
                if key in {
                    "domain",
                    "task_type",
                    "revenue_intent_override",
                    "marketing_plan_override",
                    "plan_or_execute",
                }:
                    continue
                value = crewai_result.get(key)
                if value:
                    result[key] = value
        elif crewai_strict_required(orchestration_cfg):
            raise RuntimeError("CrewAI triage required but unavailable")
        logger.info(
            "TRIAGE RESULT (marketing-plan) domain=%s task_type=%s marketing_override=%s",
            result.get("domain"),
            result.get("task_type"),
            result.get("marketing_plan_override"),
        )
        return result

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
    if crewai_result:
        for key in result.keys():
            value = crewai_result.get(key)
            if value:
                result[key] = value
    elif crewai_strict_required(orchestration_cfg):
        raise RuntimeError("CrewAI triage required but unavailable")

    result["revenue_intent_override"] = False
    result["marketing_plan_override"] = False
    result["exploration_mode"] = detect_exploration_intent(owner_text)
    logger.info(
        "TRIAGE RESULT domain=%s task_type=%s revenue_override=%s exploration_mode=%s",
        result.get("domain"),
        result.get("task_type"),
        result.get("revenue_intent_override"),
        result.get("exploration_mode"),
    )
    return result
