# tests/test_phase9_5_owner_projects.py — Phase 9.5: project model and drill-down
from __future__ import annotations

from app.services.project_queries import (
    list_projects,
    get_project_overview,
    get_project_health,
    get_project_risks,
    get_project_decision_queue,
    get_project_tasks,
    get_project_pending_approvals,
    get_project_recent_artifacts,
)
from app.presenters.project_presenters import (
    present_project_list,
    present_project_overview,
    present_project_health,
    present_project_tasks,
    present_project_approvals,
    present_project_artifacts,
    present_project_risks,
    present_project_decision_queue,
    format_project_list_text,
    format_project_card_text,
)


def test_project_list_returns_grouped_items(db_session):
    data = list_projects(limit=50)
    assert "items" in data
    assert "count" in data
    assert isinstance(data["items"], list)
    for p in data["items"]:
        assert "project_key" in p
        assert "project_label" in p
        assert p.get("status") in ("healthy", "attention_needed", "critical")
        assert "active_count" in p
        assert "pending_count" in p


def test_project_overview_contains_health_and_counts(db_session):
    overview = get_project_overview("general")
    assert "project_key" in overview
    assert "health" in overview
    assert "active_count" in overview
    assert "pending_count" in overview
    assert "recent_artifacts_count" in overview
    h = overview["health"]
    assert "status" in h
    assert "reason" in h


def test_project_risks_and_decision_queue_exist(db_session):
    risks = get_project_risks("general", limit=5)
    assert "items" in risks
    assert "count" in risks
    queue = get_project_decision_queue("general", limit=5)
    assert "items" in queue
    assert "count" in queue
    for q in queue.get("items", []):
        assert "task_id" in q or "reason" in q
        assert "suggested_next_action" in q or "reason" in q


def test_project_presenters_return_renderable_data():
    list_data = present_project_list({"items": [{"project_key": "general", "project_label": "general", "status": "healthy", "reason": "OK", "active_count": 0, "pending_count": 0, "rework_signals": 0, "long_running": 0}], "count": 1})
    assert list_data["items"]
    assert list_data["items"][0]["project_key"] == "general"

    overview_data = present_project_overview({"project_key": "x", "project_label": "x", "health": {"status": "healthy"}, "active_count": 0, "pending_count": 0, "recent_artifacts_count": 0})
    assert overview_data["project_key"] == "x"
    assert "health" in overview_data

    health_data = present_project_health({"project_key": "x", "status": "healthy", "reason": "OK", "active_count": 0, "pending_count": 0})
    assert health_data["status"] == "healthy"

    tasks_data = present_project_tasks({"items": [], "count": 0})
    assert "items" in tasks_data and "count" in tasks_data

    risks_data = present_project_risks({"items": [{"risk_type": "a", "reason": "b", "suggested_action": "c"}], "count": 1})
    assert len(risks_data["items"]) == 1

    text = format_project_list_text(list_data)
    assert "Проекты" in text or "general" in text
    card_text = format_project_card_text({"overview": overview_data, "health": health_data, "risks": {"items": []}, "decision_queue": {"items": []}, "project_key": "x"})
    assert "Проект" in card_text or "x" in card_text


def test_owner_projects_route_is_wired():
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    client = TestClient(app)
    r = client.get("/owner/projects")
    assert r.status_code == 401


def test_owner_project_detail_route_is_wired():
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    client = TestClient(app)
    r = client.get("/owner/project/general")
    assert r.status_code == 401


def test_owner_project_commands_are_wired():
    import app.bot.handlers as h
    assert hasattr(h, "handle_owner_projects")
    assert hasattr(h, "handle_owner_project")


def test_dashboard_links_to_project_views():
    from pathlib import Path
    dashboard_path = Path(__file__).resolve().parent.parent / "app" / "dashboard" / "templates" / "owner_dashboard.html"
    content = dashboard_path.read_text(encoding="utf-8")
    assert "/owner/projects" in content
    assert "owner/project/" in content
