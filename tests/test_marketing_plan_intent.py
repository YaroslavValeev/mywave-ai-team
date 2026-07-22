"""Tests for marketing plan intent + handoff draft."""

from app.orchestrator.marketing_intent import (
    build_zero_budget_marketing_draft,
    detect_marketing_plan_intent,
)
from app.orchestrator.pipeline import _build_handoff_payload


def test_detect_mywave_wake_marketing_zero_budget():
    text = (
        '#TASK У меня есть проект "MyWave Wake", '
        "создай для него маркетинговый-рекламный план за 0 рублей."
    )
    assert detect_marketing_plan_intent(text) is True


def test_detect_not_marketing_bugfix():
    assert detect_marketing_plan_intent("Починить баг деплоя на прод") is False


def test_marketing_handoff_contains_plan_sections():
    triage = {
        "domain": "MEDIA_OPS",
        "task_type": "marketing_plan",
        "criticality": "MEDIUM",
        "plan_or_execute": "PLAN",
        "execute_gate": "OWNER_APPROVAL_IF_PUBLISH",
        "marketing_plan_override": True,
    }
    payload = _build_handoff_payload(
        step_name="CONTENT",
        task_id=99,
        triage_result=triage,
        owner_brief='проект "MyWave Wake" маркетинг план 0 руб',
        attachment_context=[],
        attachment_rule_excerpts=[],
        next_action="BRAND",
        previous_step=None,
    )
    joined = "\n".join(payload["summary"])
    assert "Контент-план" in joined or "Неделя" in joined
    assert "deliverable::zero_budget_marketing_plan" in payload["artifacts"]
    draft = build_zero_budget_marketing_draft('проект "MyWave Wake"')
    assert draft["owner_tomorrow"]
    assert "MyWave Wake" in draft["audience_offer"][0]
