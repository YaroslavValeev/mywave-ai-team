# tests/test_phase9_4_owner_dashboard.py — Phase 9.4: owner dashboard baseline
from __future__ import annotations

from unittest.mock import patch

from app.services.owner_dashboard import (
    get_dashboard_overview,
    get_dashboard_next_actions,
    get_dashboard_blockers,
    get_dashboard_decision_queue,
    get_dashboard_project_health,
    get_dashboard_recent_artifacts,
    get_dashboard_digest_preview,
)
from app.presenters.owner_dashboard_presenters import (
    present_dashboard_overview,
    present_dashboard_next_actions,
    present_dashboard_blockers,
    present_dashboard_decision_queue,
    present_dashboard_project_health,
    present_dashboard_recent_artifacts,
    present_dashboard_digest_preview,
)


def test_dashboard_overview_shape(db_session):
    data = get_dashboard_overview()
    assert "state" in data
    assert "transport_mode" in data
    assert "molt_ok" in data
    assert "molt_message" in data
    assert "active_tasks_count" in data
    assert "pending_approvals_count" in data
    assert "recent_artifacts_count" in data


def test_dashboard_aggregates_next_actions_blockers_and_decisions(db_session):
    next_data = get_dashboard_next_actions(limit=5)
    assert "items" in next_data
    assert "count" in next_data
    blockers_data = get_dashboard_blockers(limit=5)
    assert "blockers_count" in blockers_data
    assert "items" in blockers_data
    queue_data = get_dashboard_decision_queue(limit=5)
    assert "items" in queue_data
    assert "count" in queue_data


def test_dashboard_presenters_return_renderable_view_models():
    overview = present_dashboard_overview({
        "state": "OK",
        "transport_mode": "local",
        "molt_ok": True,
        "molt_message": "n/a",
        "active_tasks_count": 0,
        "pending_approvals_count": 0,
        "recent_artifacts_count": 0,
    })
    assert "status_cue" in overview
    assert overview["status_cue"] in ("OK", "Pending approvals", "DEGRADED", "HTTP runtime down", "Attention needed")

    next_vm = present_dashboard_next_actions({"items": [], "count": 0})
    assert "items" in next_vm and "count" in next_vm

    blockers_vm = present_dashboard_blockers({"blockers_count": 0, "items": []})
    assert "items" in blockers_vm and "blockers_count" in blockers_vm

    queue_vm = present_dashboard_decision_queue({"items": [], "count": 0})
    assert "items" in queue_vm

    health_vm = present_dashboard_project_health({"items": [], "count": 0})
    assert "items" in health_vm

    artifacts_vm = present_dashboard_recent_artifacts({"items": [], "count": 0})
    assert "items" in artifacts_vm

    digest_vm = present_dashboard_digest_preview({
        "weekly": {"window_days": 7},
        "monthly": {"window_days": 30},
    })
    assert "weekly" in digest_vm and "monthly" in digest_vm
    assert digest_vm["weekly"].get("window_days") == 7
    assert digest_vm["monthly"].get("window_days") == 30


def test_dashboard_route_is_wired():
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    client = TestClient(app)
    # Without auth we expect 401
    r = client.get("/owner")
    assert r.status_code == 401


def test_dashboard_shows_degraded_state_when_molt_down():
    with patch("app.services.owner_dashboard.get_system_status_summary") as m:
        m.return_value = {
            "state": "DEGRADED",
            "transport_mode": "http",
            "molt_ok": False,
            "molt_message": "down (Connection refused)",
            "active_tasks_count": 2,
            "pending_approvals_count": 0,
            "recent_artifacts_count": 0,
        }
        raw = get_dashboard_overview()
        vm = present_dashboard_overview(raw)
        assert vm["state"] == "DEGRADED"
        assert vm["molt_ok"] is False
        assert vm["status_cue"] in ("DEGRADED", "HTTP runtime down")


def test_dashboard_recent_artifacts_block_has_expected_items(db_session):
    data = get_dashboard_recent_artifacts(limit=5)
    assert "items" in data
    assert "count" in data
    for item in data["items"]:
        assert "task_id" in item
        assert "summary" in item
        assert "report_path" in item
        assert "updated_at" in item


def test_dashboard_digest_preview_exists():
    data = get_dashboard_digest_preview()
    assert "weekly" in data
    assert "monthly" in data
    assert data["weekly"].get("window_days") == 7
    assert data["monthly"].get("window_days") == 30
