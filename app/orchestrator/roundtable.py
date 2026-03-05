# app/orchestrator/roundtable.py — risk-table
from typing import Optional

from app.config import get_routing


def run_roundtable(task_id: int, triage_result: dict, pipeline_result: dict, repo) -> dict:
    """
    Формирует risk-table: issue, severity, impact, recommendation, owner_approval_needed.
    """
    routing = get_routing()
    domain = triage_result.get("domain", "PRODUCT_DEV")
    task_type = triage_result.get("task_type", "feature_delivery")

    domains_cfg = routing.get("domains", {})
    reviewers = []
    if domain in domains_cfg:
        task_types_cfg = domains_cfg[domain].get("task_types", {})
        if task_type in task_types_cfg:
            reviewers = task_types_cfg[task_type].get("roundtable", ["RC", "QA"])

    if not reviewers:
        reviewers = ["RC", "QA"]

    risk_table = [
        {
            "issue": "Draft v1 requires Owner review before execute",
            "severity": "MEDIUM",
            "impact": "Standard process",
            "evidence": "Pipeline completed",
            "recommendation": "Proceed to Court",
            "owner_approval_needed": triage_result.get("plan_or_execute") == "EXECUTE",
        },
    ]

    repo.update_task(task_id, risk_table_json=risk_table)
    return {"risk_table": risk_table, "reviewers": reviewers}
