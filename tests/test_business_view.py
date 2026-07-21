# Юнит-тесты слоя представления Business View (без БД).
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.dashboard.business_view import (
    artifact_action_hints,
    business_goal_display,
    execution_from_scenario_dict,
    exploration_waiting_for_scenario,
    friendly_current_phase,
    friendly_phase_name,
    mission_headline,
    mission_list_row,
    next_business_step_text,
    owner_workstream_from_intake_brief,
    owner_workstream_label,
    parse_view_mode,
    project_impact_blurb,
)
from app.intake.schemas import BusinessAction, TaskBrief


def _task(**kwargs) -> SimpleNamespace:
    defaults = dict(
        id=1,
        owner_text="",
        business_type=None,
        domain=None,
        task_type=None,
        business_action_json=None,
        business_outcome=None,
        status="DONE",
        impact_level=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _proj(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def test_owner_workstream_wakesafari_revenue_json():
    t = _task(
        domain="PRODUCT_DEV",
        task_type="feature_delivery",
        business_type="revenue",
        business_action_json={"business_unit": "wakesafari"},
    )
    assert "EVENT" in owner_workstream_label(t, None)


def test_owner_workstream_events_domain():
    t = _task(domain="EVENTS", task_type="event_runbook", business_type="ops")
    assert owner_workstream_label(t, None) == "EVENT"


def test_owner_workstream_launch_from_gm_template():
    t = _task(
        domain="PRODUCT_DEV",
        owner_text="Подготовить стратегию запуска продукта",
        business_action_json={"gm_decision": {"workflow_template": "business"}},
    )
    assert owner_workstream_label(t, None) == "LAUNCH"


def test_friendly_phase_business():
    assert friendly_phase_name("pipeline", "business") == "План"
    assert friendly_phase_name("court", "business") == "Решение"
    assert friendly_phase_name("exploration", "business") == "Сценарии"
    assert friendly_phase_name("pipeline", "system") == "pipeline"


def test_phase_index_exploration_wait_owner_not_past_court():
    from app.dashboard.app import _phase_index

    t = _task(
        status="WAIT_OWNER",
        business_action_json={
            "exploration": {"exploration_mode": True, "options": [{"id": "s1"}]}
        },
    )
    assert _phase_index(t) == 1


def test_exploration_waiting_for_scenario_and_friendly_phase():
    t = _task(
        status="WAIT_OWNER",
        business_action_json={
            "exploration": {"exploration_mode": True, "options": [{"id": "s1"}], "selected_option_id": ""}
        },
    )
    assert exploration_waiting_for_scenario(t) is True
    wf = {"current_step": "exploration"}
    assert "Сценарии" in friendly_current_phase(t, wf, "business")

    t2 = _task(
        status="WAIT_OWNER",
        business_action_json={
            "exploration": {"exploration_mode": True, "options": [{"id": "s1"}], "selected_option_id": "s1"}
        },
    )
    assert exploration_waiting_for_scenario(t2) is False


def test_next_business_step_fallback():
    t = _task(business_action_json={})
    assert "Согласуйте с Owner" in next_business_step_text(t)


def test_next_business_step_from_gm():
    t = _task(
        business_action_json={"gm_decision": {"next_business_step": "Найти 5 партнёров"}},
    )
    assert next_business_step_text(t) == "Найти 5 партнёров"


def test_mission_headline_strips_task_hash():
    t = _task(owner_text="#TASK Подготовить оффер\nдетали")
    assert mission_headline(t).startswith("Подготовить оффер")


def test_mission_headline_intake_title():
    t = _task(
        owner_text="#TASK x",
        business_action_json={"intake_title": "WakeSafari Launch Plan"},
    )
    assert mission_headline(t) == "WakeSafari Launch Plan"


def test_project_impact_blurb():
    t = _task()
    p = _proj(stage="validation", owner_focus_level="high", business_goal="")
    s = project_impact_blurb(t, p, {})
    assert "validation" in s.lower() or "Стадия" in s


def test_business_goal_from_json_hint():
    t = _task(business_action_json={"business_goal_hint": "Рост спонсоров"})
    assert business_goal_display(t, None) == "Рост спонсоров"


def test_artifact_hints_non_empty():
    h = artifact_action_hints("COURT_VERDICT", "EVENT · REVENUE")
    assert len(h) >= 2


def test_execution_from_scenario_dict_and_next_step():
    t = _task(
        status="EXECUTION_READY",
        business_action_json={
            "execution_from_scenario": {
                "system_note": "Можно запускать через Cursor.",
                "cursor_prompts": [{"agent": "Collector", "prompt": "x"}],
            }
        },
    )
    assert execution_from_scenario_dict(t).get("cursor_prompts")
    assert "Cursor" in next_business_step_text(t)


def test_friendly_phase_execution_ready():
    t = _task(status="EXECUTION_READY")
    wf = {"current_step": "idle", "progress_done": 1, "progress_total": 6, "status": "waiting_owner"}
    assert "Cursor" in friendly_current_phase(t, wf, "business")


def test_mission_list_row_has_execution_ready_flag():
    t = _task(
        status="EXECUTION_READY",
        business_action_json={"execution_from_scenario": {"project_structure": ["a/"]}},
    )
    row = mission_list_row(t, None, {"progress_done": 1, "progress_total": 6, "status": "waiting_owner"})
    assert row["has_execution_ready"] is True


def test_owner_workstream_from_intake_brief_wakesafari():
    brief = TaskBrief(
        title="Стратегия",
        input_summary="WakeSafari спонсоры",
        business_unit="wakesafari",
        business_type="revenue",
    )
    act = BusinessAction(action_type="revenue", expected_outcome="x", impact_level="high")
    assert "EVENT" in owner_workstream_from_intake_brief(brief, act)
