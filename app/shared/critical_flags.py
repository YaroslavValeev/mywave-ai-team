# app/shared/critical_flags.py — CRITICAL_EXECUTE флаги
# Если любой флаг = true → требуй Approve Owner через Telegram

CRITICAL_FLAGS = [
    "prod_deploy",
    "public_publish",
    "money_or_pricing",
    "pii_or_sensitive",
    "legal_commitment",
]


def check_critical_execute(flags: dict) -> bool:
    """Возвращает True, если требуется Approve Owner."""
    return any(flags.get(f, False) for f in CRITICAL_FLAGS)


def infer_flags_from_task(
    domain: str,
    task_type: str,
    execute_gate: str,
    plan_or_execute: str,
) -> dict:
    """Выводит флаги из контекста задачи."""
    flags = {f: False for f in CRITICAL_FLAGS}
    if plan_or_execute != "EXECUTE":
        return flags

    gate_lower = (execute_gate or "").lower()
    task_lower = (task_type or "").lower()

    if "prod" in gate_lower or "deploy" in task_lower or task_type == "deploy_prod":
        flags["prod_deploy"] = True
    if "publish" in gate_lower or "publish" in task_lower or task_type == "publish_major":
        flags["public_publish"] = True
    if "money" in gate_lower or "contract" in gate_lower or "pricing" in task_lower:
        flags["money_or_pricing"] = True
    if "pii" in gate_lower or "sensitive" in gate_lower or "pii" in task_lower:
        flags["pii_or_sensitive"] = True
    if "legal" in gate_lower or "contract" in gate_lower:
        flags["legal_commitment"] = True

    return flags
