# app/orchestrator/roundtable.py — risk-table
from app.config import get_routing


def run_roundtable(task_id: int, triage_result: dict, pipeline_result: dict, repo, control=None) -> dict:
    """
    Формирует risk-table: issue, severity, impact, recommendation, owner_approval_needed.
    """
    if control:
        control.set_phase("roundtable", message="Команда собирает риски и рекомендации.", current_step="RC")
        control.check_cancelled()

    routing = get_routing()
    domain = triage_result.get("domain", "PRODUCT_DEV")
    task_type = triage_result.get("task_type", "feature_delivery")
    criticality = triage_result.get("criticality", "MEDIUM")
    plan_or_execute = triage_result.get("plan_or_execute", "PLAN")
    execute_gate = triage_result.get("execute_gate", "OWNER_APPROVAL_IF_PROD")

    domains_cfg = routing.get("domains", {})
    reviewers = []
    if domain in domains_cfg:
        task_types_cfg = domains_cfg[domain].get("task_types", {})
        if task_type in task_types_cfg:
            reviewers = task_types_cfg[task_type].get("roundtable", ["RC", "QA"])

    if not reviewers:
        reviewers = ["RC", "QA"]

    handoffs = pipeline_result.get("handoffs", [])
    handoff_steps = [handoff.get("step", "-") for handoff in handoffs]
    gate_lower = (execute_gate or "").lower()
    owner_approval_needed = plan_or_execute == "EXECUTE" or "approval" in gate_lower

    risk_table = []

    if owner_approval_needed:
        risk_table.append(
            _risk(
                issue="Owner approval gate blocks direct execute",
                severity="CRITICAL" if criticality == "CRITICAL" else "HIGH",
                impact="Execution cannot proceed automatically.",
                evidence=f"plan_or_execute={plan_or_execute}; execute_gate={execute_gate}",
                recommendation="Keep task in WAIT_OWNER until owner approves the execute path.",
                owner_approval_needed=True,
            )
        )

    if criticality in {"HIGH", "CRITICAL"}:
        risk_table.append(
            _risk(
                issue="High-impact task needs stronger validation",
                severity=criticality,
                impact="Regression, public, or delivery impact is above baseline.",
                evidence=f"criticality={criticality}; reviewers={', '.join(reviewers)}",
                recommendation="Review handoffs and confirm acceptance criteria before closing the task.",
                owner_approval_needed=owner_approval_needed,
            )
        )

    if len(handoffs) < 2:
        risk_table.append(
            _risk(
                issue="Pipeline evidence is still thin",
                severity="MEDIUM",
                impact="Court output may be too shallow for confident execution.",
                evidence=f"handoffs={len(handoffs)}; steps={', '.join(handoff_steps) or '-'}",
                recommendation="Expand the owner brief or rerun with a more specific task statement.",
                owner_approval_needed=False,
            )
        )

    if "prod" in gate_lower or task_type == "deploy_prod":
        risk_table.append(
            _risk(
                issue="Production path needs rollback and verification",
                severity="HIGH",
                impact="Failed deployment can affect live workflows.",
                evidence=f"execute_gate={execute_gate}",
                recommendation="Prepare rollback, backup, and post-deploy health checks.",
                owner_approval_needed=owner_approval_needed,
            )
        )

    if any(token in gate_lower for token in ("publish", "public")):
        risk_table.append(
            _risk(
                issue="Public output requires publication review",
                severity="HIGH" if owner_approval_needed else "MEDIUM",
                impact="Incorrect public messaging can create brand or trust damage.",
                evidence=f"execute_gate={execute_gate}",
                recommendation="Review content, approvals, and publication timing before release.",
                owner_approval_needed=owner_approval_needed,
            )
        )

    if any(token in gate_lower for token in ("money", "contract", "legal")):
        risk_table.append(
            _risk(
                issue="Commercial or legal exposure present",
                severity="HIGH",
                impact="Pricing, commitments, or contract language may have downstream obligations.",
                evidence=f"execute_gate={execute_gate}",
                recommendation="Keep owner in the decision loop and validate commercial assumptions.",
                owner_approval_needed=True,
            )
        )

    if any(token in gate_lower for token in ("pii", "sensitive", "video")):
        risk_table.append(
            _risk(
                issue="Sensitive data handling needs explicit review",
                severity="HIGH",
                impact="Privacy or access-control mistakes can leak protected data.",
                evidence=f"execute_gate={execute_gate}",
                recommendation="Confirm redaction, retention, and access boundaries before execution.",
                owner_approval_needed=True,
            )
        )

    if not risk_table:
        risk_table.append(
            _risk(
                issue="No blocking issues found in configured roundtable",
                severity="LOW",
                impact="Task can move forward on the current evidence set.",
                evidence=f"reviewers={', '.join(reviewers)}; handoffs={len(handoffs)}",
                recommendation="Proceed to Court and keep the owner informed.",
                owner_approval_needed=False,
            )
        )

    repo.update_task(task_id, risk_table_json=risk_table)
    if control:
        control.check_cancelled()
    return {"risk_table": risk_table, "reviewers": reviewers, "handoff_steps": handoff_steps}


def _risk(
    *,
    issue: str,
    severity: str,
    impact: str,
    evidence: str,
    recommendation: str,
    owner_approval_needed: bool,
) -> dict:
    return {
        "issue": issue,
        "severity": severity,
        "impact": impact,
        "evidence": evidence,
        "recommendation": recommendation,
        "owner_approval_needed": owner_approval_needed,
    }
