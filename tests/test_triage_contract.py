import pytest

from app.config import get_routing
from app.orchestrator.triage import _explicit_project_triage, _merge_crewai_triage
from app.orchestrator.triage_snapshot import _revenue_locked


def test_unknown_llm_domain_does_not_override_canonical_route():
    base = {
        "domain": "GAME",
        "task_type": "economy_balance",
        "criticality": "HIGH",
        "plan_or_execute": "PLAN",
        "execute_gate": "OWNER_APPROVAL_IF_PUBLISH_OR_MONEY",
    }

    result = _merge_crewai_triage(
        base,
        {
            "domain": "economic-planning",
            "task_type": "plan",
            "criticality": "medium",
            "plan_or_execute": "plan",
            "execute_gate": "",
        },
        get_routing(),
    )

    assert result["domain"] == "GAME"
    assert result["task_type"] == "economy_balance"
    assert result["criticality"] == "HIGH"
    assert result["plan_or_execute"] == "PLAN"
    assert result["execute_gate"] == "OWNER_APPROVAL_IF_PUBLISH_OR_MONEY"


def test_valid_llm_route_is_accepted_as_one_canonical_pair():
    base = {
        "domain": "PRODUCT_DEV",
        "task_type": "feature_delivery",
        "criticality": "MEDIUM",
        "plan_or_execute": "PLAN",
        "execute_gate": "OWNER_APPROVAL_IF_PROD",
    }

    result = _merge_crewai_triage(
        base,
        {
            "domain": "RND_EXTREME",
            "task_type": "judge_console_mvp",
            "criticality": "critical",
            "plan_or_execute": "execute",
            "execute_gate": "OWNER_APPROVAL_ALWAYS",
        },
        get_routing(),
    )

    assert result == {
        "domain": "RND_EXTREME",
        "task_type": "judge_console_mvp",
        "criticality": "CRITICAL",
        "plan_or_execute": "EXECUTE",
        "execute_gate": "OWNER_APPROVAL_IF_VIDEO_PII_OR_PUBLIC",
    }


def test_locked_business_route_cannot_be_reclassified_by_llm():
    base = {
        "domain": "BUSINESS",
        "task_type": "revenue_execution",
        "criticality": "HIGH",
        "plan_or_execute": "EXECUTE",
        "execute_gate": "OWNER_APPROVAL_IF_CONTRACTS_OR_MONEY",
    }

    result = _merge_crewai_triage(
        base,
        {
            "domain": "MEDIA_OPS",
            "task_type": "marketing_plan",
            "criticality": "LOW",
            "plan_or_execute": "PLAN",
        },
        get_routing(),
        locked_keys={"domain", "task_type", "plan_or_execute"},
    )

    assert result["domain"] == "BUSINESS"
    assert result["task_type"] == "revenue_execution"
    assert result["plan_or_execute"] == "EXECUTE"
    assert result["criticality"] == "HIGH"


@pytest.mark.parametrize(
    "owner_text,expected",
    [
        ("SnowPolia: баланс экономики", ("GAME", "economy_balance")),
        ("Sponsorship Platform: scoring спонсоров", ("SPONSOR_PLATFORM", "mvp_scoring")),
        ("ExtremeMedia: Judge Console", ("RND_EXTREME", "judge_console_mvp")),
    ],
)
def test_explicit_project_route_has_priority_over_generic_intent(owner_text, expected):
    result = _explicit_project_triage(owner_text, get_routing())

    assert result is not None
    assert (result["domain"], result["task_type"]) == expected


def test_explicit_sponsorship_project_is_not_revenue_locked():
    owner_text = "Sponsorship Platform: scoring спонсоров и договорные поля"

    assert _revenue_locked({}, {"revenue_intent_override": False}, owner_text) is False
