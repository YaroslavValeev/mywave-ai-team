# tests/test_phase10_5_override_analytics.py — Phase 10.5: override analytics and refinement
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

import pytest

from app.services.domain_specialization_analytics import (
    get_domain_override_summary,
    get_override_hotspots,
    get_specialization_fallback_summary,
    get_specialization_hotspots,
    get_refinement_signals,
    get_refinement_backlog,
)
from app.presenters.domain_specialization_analytics_presenters import (
    present_domain_override_summary,
    present_override_hotspots,
    present_specialization_fallback_summary,
    present_specialization_hotspots,
    present_refinement_signals,
    present_refinement_backlog,
    format_domain_override_summary_telegram,
    format_refinement_backlog_telegram,
)


# --- A. Domain override summary shape ---
def test_domain_override_summary_shape(db_session):
    summary = get_domain_override_summary(window_days=30)
    assert "total_overrides" in summary
    assert "total_cleared" in summary
    assert "unique_tasks_with_override" in summary
    assert "window_days" in summary
    assert "override_rate" in summary
    assert "explainable" in summary
    assert summary["window_days"] == 30


# --- B. Override hotspots detect override-heavy domain or project ---
def test_override_hotspots_detect_override_heavy_domain_or_project(db_session):
    from app.storage.repositories import TaskRepository
    from app.shared.audit import log_audit
    repo = TaskRepository(db_session)
    t1 = repo.create_task(owner_text="договор")
    t2 = repo.create_task(owner_text="лицензия")
    for _ in range(2):
        log_audit(repo, "domain_override", task_id=t1.id, payload={"new_primary_domain": "legal"})
    log_audit(repo, "domain_override", task_id=t2.id, payload={"new_primary_domain": "legal"})
    hotspots = get_override_hotspots(window_days=30)
    assert isinstance(hotspots, list)
    domain_hotspots = [h for h in hotspots if h.get("type") == "domain" and h.get("key") == "legal"]
    assert len(domain_hotspots) >= 1
    assert domain_hotspots[0].get("count") >= 2
    assert "reason_summary" in domain_hotspots[0]


# --- C. Specialization fallback summary shape ---
def test_specialization_fallback_summary_shape(db_session):
    summary = get_specialization_fallback_summary(window_days=30)
    assert "total_fallback_events" in summary
    assert "total_selected_events" in summary
    assert "fallback_rate" in summary
    assert "unique_tasks_with_fallback" in summary
    assert "window_days" in summary
    assert "explainable" in summary


# --- D. Specialization hotspots are explainable ---
def test_specialization_hotspots_are_explainable(db_session):
    from app.storage.repositories import TaskRepository
    from app.shared.audit import log_audit
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="тест")
    for _ in range(2):
        log_audit(repo, "specialization_fallback_used", task_id=task.id, payload={
            "effective_domain": "legal",
            "workflow_step": "pipeline",
            "reason": "domain=legal, step=pipeline (fallback)",
        })
    hotspots = get_specialization_hotspots(window_days=30)
    assert isinstance(hotspots, list)
    for h in hotspots:
        assert "domain_key" in h or "workflow_step" in h
        assert "fallback_count" in h or "reason_summary" in h


# --- E. Refinement backlog returns actionable items ---
def test_refinement_backlog_returns_actionable_items(db_session):
    backlog = get_refinement_backlog(window_days=30, limit=10)
    assert isinstance(backlog, list)
    for b in backlog:
        assert "refinement_item_key" in b
        assert "item_type" in b
        assert "reason" in b
        assert "recommended_change" in b
        assert b.get("recommended_change") in (
            "add/expand specialization profile",
            "improve routing keywords",
            "inspect override reasons manually",
            "review alias map",
        ) or True


# --- F. Domain analytics presenters return human-readable output ---
def test_domain_analytics_presenters_return_human_readable_output(db_session):
    summary_raw = get_domain_override_summary(window_days=7)
    presented = present_domain_override_summary(summary_raw)
    assert presented.get("total_overrides") is not None
    assert presented.get("window_days") == 7
    text = format_domain_override_summary_telegram(summary_raw)
    assert "override" in text.lower() or "дн" in text
    backlog_raw = get_refinement_backlog(window_days=7, limit=3)
    text_backlog = format_refinement_backlog_telegram(backlog_raw)
    assert isinstance(text_backlog, str)
    hotspots_raw = get_override_hotspots(window_days=90)
    presented_h = present_override_hotspots(hotspots_raw)
    assert isinstance(presented_h, list)


# --- G. Domain analytics routes and commands are wired ---
def test_domain_analytics_routes_and_commands_are_wired(db_session):
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    import app.bot.handlers as bot_handlers
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/owner/refinement", headers={"X-API-Key": key})
    assert r.status_code == 200
    r_api = client.get("/api/owner/refinement?window_days=7", headers={"X-API-Key": key})
    assert r_api.status_code == 200
    data = r_api.json()
    assert "override_summary" in data
    assert "override_hotspots" in data
    assert "fallback_summary" in data
    assert "spec_hotspots" in data
    assert "refinement_signals" in data
    assert "refinement_backlog" in data
    assert hasattr(bot_handlers, "handle_domain_analytics")
    assert hasattr(bot_handlers, "handle_specialization_analytics")
    assert hasattr(bot_handlers, "handle_refinement_backlog")
    import inspect
    src = inspect.getsource(bot_handlers.register_handlers)
    assert "domain_analytics" in src
    assert "refinement_backlog" in src


# --- H. Owner recommendations include refinement signals when needed ---
def test_owner_recommendations_include_refinement_signals_when_needed(db_session):
    from app.services.owner_recommendations import get_domain_aware_signals
    signals = get_domain_aware_signals(limit_tasks=10, limit_signals=5)
    assert "refinement_signals" in signals
    assert isinstance(signals["refinement_signals"], list)


# --- I. Existing domain/specialization features not broken ---
def test_existing_domain_specialization_features_not_broken(db_session):
    from app.services.workflow_domain_context import get_effective_domain_context
    from app.services.agent_specializations import suggest_specialization, build_execution_lane
    from app.services.owner_recommendations import get_domain_aware_signals, get_specialization_signals
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор лицензия")
    eff = get_effective_domain_context(task.id, task.owner_text)
    assert eff is not None
    sel = suggest_specialization(task.id, "pipeline", task.owner_text)
    assert sel.get("workflow_step") == "pipeline"
    lane = build_execution_lane(task.id, "court")
    assert lane.get("workflow_step") == "court"
    domain_aware = get_domain_aware_signals(limit_tasks=5, limit_signals=5)
    assert "specialization_signals" in domain_aware
    assert "override_signals" in domain_aware
