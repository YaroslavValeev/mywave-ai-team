from __future__ import annotations

from types import SimpleNamespace

from app.metrics import calculate_outcome_metrics, compute_outcome_metrics


def _task(**kwargs):
    values = {
        "business_action_json": {},
        "business_outcome": "",
        "rework_cycles": 0,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def _event(event_type: str, **payload):
    return SimpleNamespace(event_type=event_type, payload_json=payload)


def test_explicit_outcome_metrics_are_authoritative():
    task = _task(
        business_outcome="Получены три подтверждённых лида",
        rework_cycles=1,
        business_action_json={
            "outcome_metrics": {
                "owner_minutes": 18,
                "autonomous_actions": 7,
                "total_actions": 9,
                "rework_count": 2,
                "owner_hours_saved": 2.75,
            }
        },
    )

    result = calculate_outcome_metrics(task, [_event("OWNER_REWORK", owner_minutes=90)])

    assert result == {
        "owner_minutes": 18.0,
        "autonomous_actions": 7,
        "total_actions": 9,
        "rework_count": 2,
        "business_outcome": "Получены три подтверждённых лида",
        "autonomous_completion_rate": 0.7778,
        "owner_hours_saved": 2.75,
    }


def test_audit_events_supply_actions_owner_time_and_rework():
    task = _task(business_outcome="PR создан и тесты прошли", rework_cycles=1)
    events = [
        _event("task_created", source="api"),
        _event("triage_done", source="system", estimated_manual_minutes=20),
        _event("pipeline_done", actor="agent", estimated_manual_minutes=45),
        _event("OWNER_REWORK", actor="owner", owner_minutes=7),
        _event("roundtable_done", source="system", estimated_manual_minutes=25),
        _event("OWNER_APPROVED", actor="owner", duration_minutes=3),
        _event("validation_done", source="automation", estimated_manual_minutes=30),
        _event("api_request", source="owner"),
    ]

    result = calculate_outcome_metrics(task, events)

    assert result["owner_minutes"] == 10.0
    assert result["autonomous_actions"] == 4
    assert result["total_actions"] == 6
    assert result["rework_count"] == 1
    assert result["autonomous_completion_rate"] == 0.6667
    assert result["owner_hours_saved"] == 1.8333


def test_structured_actions_take_precedence_over_duplicate_audit_events():
    task = {
        "business_action_json": {
            "execution_actions": [
                {"agent": "developer", "estimated_manual_minutes": 40},
                {"performed_by": "owner", "estimated_manual_minutes": 10},
                {"autonomous": True, "estimated_manual_minutes": 30},
            ],
            "owner_minutes": 15,
            "action_instance": {"status": "done", "result_summary": "Изменение внедрено"},
        },
        "rework_cycles": 0,
    }

    result = compute_outcome_metrics(task, [_event("pipeline_done"), _event("pipeline_done")])

    assert result["total_actions"] == 3
    assert result["autonomous_actions"] == 2
    assert result["business_outcome"] == "Изменение внедрено"
    assert result["owner_hours_saved"] == 1.0833


def test_empty_and_malformed_values_are_safe_and_do_not_invent_savings():
    task = _task(
        business_action_json={
            "outcome_metrics": {
                "owner_minutes": "unknown",
                "autonomous_actions": -3,
                "total_actions": None,
            }
        },
        rework_cycles=None,
    )

    result = calculate_outcome_metrics(task, [None, {}, _event("chat_message")])

    assert result == {
        "owner_minutes": 0.0,
        "autonomous_actions": 0,
        "total_actions": 0,
        "rework_count": 0,
        "business_outcome": "",
        "autonomous_completion_rate": 0.0,
        "owner_hours_saved": 0.0,
    }
