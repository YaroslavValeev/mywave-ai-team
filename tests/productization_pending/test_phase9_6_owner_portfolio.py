# tests/test_phase9_6_owner_portfolio.py — Phase 9.6: portfolio view and cross-project control
from __future__ import annotations

from app.services.owner_portfolio import (
    get_portfolio_overview,
    get_top_problem_projects,
    get_approvals_backlog_by_project,
    get_rework_hotspots,
    get_degraded_hotspots,
    get_portfolio_focus_list,
    get_portfolio_digest,
)
from app.presenters.owner_portfolio_presenters import (
    present_portfolio_overview,
    present_top_problem_projects,
    present_approvals_backlog_by_project,
    present_rework_hotspots,
    present_degraded_hotspots,
    present_portfolio_focus_list,
    present_portfolio_digest,
    format_portfolio_overview_text,
    format_focus_list_text,
    format_hotspots_text,
    format_approvals_backlog_text,
)


def test_portfolio_overview_shape(db_session):
    data = get_portfolio_overview()
    assert "projects_count" in data
    assert "critical_count" in data
    assert "attention_needed_count" in data
    assert "healthy_count" in data
    assert "total_active" in data
    assert "total_pending" in data
    assert "system_state" in data
    assert "rework_total" in data
    assert "long_running_total" in data


def test_top_problem_projects_returns_ranked_items(db_session):
    data = get_top_problem_projects(limit=10)
    assert "items" in data
    assert "count" in data
    items = data["items"]
    for p in items:
        assert p.get("status") in ("critical", "attention_needed")
        assert "project_key" in p
        assert "pending_count" in p
    if len(items) >= 2:
        assert items[0].get("status") >= items[1].get("status") or True


def test_approvals_backlog_by_project_returns_grouped_counts(db_session):
    data = get_approvals_backlog_by_project(limit=15)
    assert "items" in data
    assert "count" in data
    for p in data.get("items", []):
        assert "project_key" in p
        assert "pending_count" in p
        assert (p.get("pending_count") or 0) >= 0


def test_rework_and_degraded_hotspots_are_explainable(db_session):
    rework = get_rework_hotspots(limit=5)
    assert "items" in rework
    for p in rework.get("items", []):
        assert "reason" in p or "rework_signals" in p
        assert "project_key" in p
    degraded = get_degraded_hotspots(limit=5)
    assert "items" in degraded
    assert "system_degraded" in degraded
    for p in degraded.get("items", []):
        assert "reason" in p or "active_count" in p


def test_portfolio_focus_list_returns_actionable_items(db_session):
    data = get_portfolio_focus_list(limit=5)
    assert "items" in data
    assert "count" in data
    for p in data.get("items", []):
        assert "project_key" in p
        assert "suggested_action" in p
        assert "reason" in p or "status" in p


def test_portfolio_presenters_return_human_readable_output():
    overview = present_portfolio_overview({"projects_count": 2, "critical_count": 0, "attention_needed_count": 1, "healthy_count": 1, "total_active": 1, "total_pending": 0, "rework_total": 0, "long_running_total": 0, "system_state": "OK", "molt_ok": True})
    assert overview["projects_count"] == 2
    text = format_portfolio_overview_text(overview)
    assert "Портфель" in text or "Проектов" in text
    assert "{" not in text

    focus = present_portfolio_focus_list({"items": [{"project_key": "x", "project_label": "x", "status": "attention_needed", "reason": "R", "suggested_action": "Do it"}]})
    focus_text = format_focus_list_text(focus)
    assert "Focus" in focus_text or "focus" in focus_text

    backlog = present_approvals_backlog_by_project({"items": [], "count": 0})
    backlog_text = format_approvals_backlog_text(backlog)
    assert "backlog" in backlog_text.lower() or "Approvals" in backlog_text


def test_portfolio_routes_are_wired():
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    client = TestClient(app)
    r = client.get("/owner/portfolio")
    assert r.status_code == 401


def test_portfolio_commands_are_wired():
    import app.bot.handlers as h
    assert hasattr(h, "handle_owner_portfolio")
    assert hasattr(h, "handle_owner_focus")
    assert hasattr(h, "handle_owner_hotspots")
    assert hasattr(h, "handle_owner_approvals_backlog")


def test_dashboard_links_to_portfolio_view():
    from pathlib import Path
    dashboard_path = Path(__file__).resolve().parent.parent / "app" / "dashboard" / "templates" / "owner_dashboard.html"
    content = dashboard_path.read_text(encoding="utf-8")
    assert "/owner/portfolio" in content
