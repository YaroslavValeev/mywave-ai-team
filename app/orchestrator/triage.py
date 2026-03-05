# app/orchestrator/triage.py — определить domain, criticality, plan_or_execute
from app.config import get_routing, get_policy


# Маппинг ключевых слов на domain + task_type
DOMAIN_HINTS = {
    "site": ("PRODUCT_DEV", "feature_delivery"),
    "сайт": ("PRODUCT_DEV", "feature_delivery"),
    "деплой": ("PRODUCT_DEV", "deploy_prod"),
    "deploy": ("PRODUCT_DEV", "deploy_prod"),
    "баг": ("PRODUCT_DEV", "software_bugfix"),
    "bug": ("PRODUCT_DEV", "software_bugfix"),
    "контент": ("MEDIA_OPS", "content_pipeline"),
    "content": ("MEDIA_OPS", "content_pipeline"),
    "новости": ("MEDIA_OPS", "content_pipeline"),
    "news": ("MEDIA_OPS", "content_pipeline"),
    "публикац": ("MEDIA_OPS", "publish_major"),
    "publish": ("MEDIA_OPS", "publish_major"),
    "ивент": ("EVENTS", "event_runbook"),
    "event": ("EVENTS", "event_runbook"),
    "соревнован": ("EVENTS", "judging_rules"),
    "судь": ("EVENTS", "judging_rules"),
    "snowpolia": ("GAME", "economy_balance"),
    "снегополия": ("GAME", "economy_balance"),
    "ruza": ("RUZA", "general"),
    "extreme": ("RND_EXTREME", "judge_console_mvp"),
    "extreme media": ("RND_EXTREME", "judge_console_mvp"),
    "турьев": ("INFRA", "invest_model"),
    "хутор": ("INFRA", "invest_model"),
    "инвест": ("INFRA", "invest_model"),
    "спонсор": ("SPONSOR_PLATFORM", "mvp_scoring"),
    "книга": ("AUTHORITY_CONTENT", "book_outline"),
    "методич": ("AUTHORITY_CONTENT", "book_outline"),
    "бот": ("CLIENTOPS", "studio_bot_admin"),
    "студия": ("CLIENTOPS", "studio_bot_admin"),
}


def run_triage(owner_text: str) -> dict:
    """
    Rule-based triage. Возвращает:
    domain, task_type, criticality, plan_or_execute, execute_gate
    """
    text_lower = (owner_text or "").lower()
    routing = get_routing()
    policy = get_policy()
    plan_execute = policy.get("plan_execute_model", {})
    criticality_cfg = policy.get("criticality", {})
    execute_types = set(criticality_cfg.get("always_critical_if", []))

    domain = "PRODUCT_DEV"
    task_type = "feature_delivery"
    execute_gate = "OWNER_APPROVAL_IF_PROD"

    for hint, (d, t) in DOMAIN_HINTS.items():
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
    if any(ex in text_lower for ex in ["деплой", "deploy", "публикац", "publish", "деньги", "money", "договор", "contract"]):
        plan_or_execute = "EXECUTE"
        if task_type in execute_types or criticality == "CRITICAL":
            criticality = "CRITICAL"

    return {
        "domain": domain,
        "task_type": task_type,
        "criticality": criticality,
        "plan_or_execute": plan_or_execute,
        "execute_gate": execute_gate,
    }
