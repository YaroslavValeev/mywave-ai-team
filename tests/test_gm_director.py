# GM / Director Layer — юнит-тесты правил без LLM
from __future__ import annotations

import pytest

from app.gm_director import GMDirectorInput, decide_gm_director, gm_director_enabled
from app.intake.schemas import GMDirectorDecision, TaskBrief


def test_gm_reject_noise():
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(title="x", input_summary="ok").model_dump(),
            intake_decision="reject",
            confidence=0.95,
            intent_type="noise",
        )
    )
    assert g.action == "reject"
    assert g.execution_mode == "quick"
    assert g.risk_level == "low"


def test_gm_owner_hard_block():
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(title="t", input_summary="сделать deploy в production").model_dump(),
            intake_decision="create",
            confidence=0.8,
            intent_type="task",
            owner_hard_block_intake=True,
        )
    )
    assert g.action == "clarify"
    assert g.requires_approval is True


def test_gm_low_confidence_clarify():
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(title="t", input_summary="что-то про API").model_dump(),
            intake_decision="create",
            confidence=0.35,
            intent_type="task",
        )
    )
    assert g.action == "clarify"


def test_gm_question_to_quick_answer():
    # Без глаголов «сделай/исправь» (иначе classify считает это работой) — чистый справочный вопрос
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(
                title="Уточнение намерения",
                input_summary="что означает этот фрагмент в логах?",
            ).model_dump(),
            intake_decision="clarify",
            confidence=0.62,
            intent_type="question",
        )
    )
    assert g.action == "answer"
    assert g.execution_mode == "quick"


def test_gm_create_light_or_full():
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(title="endpoint", input_summary="Сделать endpoint для health check").model_dump(),
            intake_decision="create",
            confidence=0.75,
            intent_type="task",
        )
    )
    assert g.action == "create_task"
    assert g.execution_mode in ("light", "full")
    assert "analyst" in g.agents_plan


def test_gm_owner_keys_force_approval():
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(title="t", input_summary="обновить стратегию продукта на Q3").model_dump(),
            owner_rules_bundle={"owner_rule_keys_applied": ["strategy_change_requires_owner"]},
            intake_decision="create",
            confidence=0.8,
            intent_type="task",
        )
    )
    assert g.requires_approval is True
    assert g.execution_mode == "full"


def test_gm_high_risk_deploy():
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(title="t", input_summary="Сделать deploy в production с новым secret token").model_dump(),
            intake_decision="create",
            confidence=0.85,
            intent_type="task",
        )
    )
    assert g.risk_level == "high"
    assert g.requires_approval is True


def test_gm_attach():
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(title="дополнение", input_summary="ещё контекст по миссии").model_dump(),
            intake_decision="attach",
            confidence=0.78,
            intent_type="task",
        )
    )
    assert g.action == "attach"


def test_gm_director_enabled_env(monkeypatch):
    monkeypatch.setenv("GM_DIRECTOR_ENABLED", "false")
    assert gm_director_enabled() is False
    monkeypatch.setenv("GM_DIRECTOR_ENABLED", "true")
    assert gm_director_enabled() is True


def test_gm_decision_schema_roundtrip():
    m = GMDirectorDecision(
        execution_mode="light",
        action="create_task",
        requires_approval=False,
        agents_plan=["analyst"],
        risk_level="medium",
        explanation="x",
        next_step="y",
        business_value_hint="hint",
        next_business_step="step",
    )
    d = m.model_dump()
    assert d["execution_mode"] == "light"
    assert d["business_value_hint"] == "hint"
    assert "owner_workstream" in d


def test_gm_create_task_business_hints_and_workflow():
    g = decide_gm_director(
        GMDirectorInput(
            task_brief=TaskBrief(
                title="Стратегия WakeSafari",
                input_summary="Подготовить стратегию запуска WakeSafari и оффер для спонсоров",
                business_unit="wakesafari",
                business_type="revenue",
            ).model_dump(),
            business_action={"action_type": "revenue", "expected_outcome": "sponsors", "impact_level": "high"},
            intake_decision="create",
            confidence=0.8,
            intent_type="task",
        )
    )
    assert g.workflow_template == "business"
    assert g.business_value_hint
    assert g.next_business_step
