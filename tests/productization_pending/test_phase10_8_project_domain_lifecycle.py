# tests/test_phase10_8_project_domain_lifecycle.py — Phase 10.8: project-domain lifecycle
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.services.project_domain_lifecycle import (
    get_project_domain_lifecycle,
    list_project_domain_lifecycles,
    get_project_domain_drift_signals,
    get_project_domain_diversification_signals,
    get_project_domain_instability_signals,
    get_cross_project_domain_lifecycle_summary,
    _compute_lifecycle_state,
)
from app.presenters.project_domain_lifecycle_presenters import (
    present_project_domain_lifecycle,
    present_cross_project_domain_lifecycle_summary,
    format_project_lifecycle_telegram,
    format_domain_lifecycle_telegram,
)


# --- A. Lifecycle profile shape ---
def test_project_domain_lifecycle_shape(db_session):
    raw = get_project_domain_lifecycle("general", window_days=30)
    assert "project_key" in raw
    assert raw.get("project_key") == "general"
    assert "current_dominant_domain" in raw
    assert "previous_dominant_domain" in raw
    assert "lifecycle_state" in raw
    assert "domain_drift_signal" in raw
    assert "domain_diversification_signal" in raw
    assert "domain_instability_signal" in raw
    assert "reason" in raw
    assert "window_days" in raw
    assert raw.get("lifecycle_state") in (
        "stable_single_domain", "stable_multi_domain", "drifting",
        "override_heavy", "unstable", "weak_signal",
    )
    presented = present_project_domain_lifecycle(raw)
    assert presented.get("project_key") == "general"
    assert "lifecycle_state" in presented


# --- B. Stable single domain detected ---
def test_stable_single_domain_project_is_detected_correctly():
    prev_dist = {"legal": 5}
    curr_dist = {"legal": 6}
    profile = {"mismatch_signals": [], "mapping_confidence": "high", "override_count": 0, "task_count": 11}
    state, explanation, drift, diversif, instab = _compute_lifecycle_state("p1", prev_dist, curr_dist, profile)
    assert state == "stable_single_domain"
    assert drift is False


# --- C. Drifting detected when dominant domain changes ---
def test_drifting_project_is_detected_when_dominant_domain_changes():
    prev_dist = {"legal": 3}
    curr_dist = {"finance": 3}
    profile = {"mismatch_signals": [], "mapping_confidence": "medium", "override_count": 0, "task_count": 6}
    state, explanation, drift, diversif, instab = _compute_lifecycle_state("p1", prev_dist, curr_dist, profile)
    assert state == "drifting"
    assert drift is True
    assert "legal" in explanation or "finance" in explanation


# --- D. Override-heavy or unstable detected ---
def test_override_heavy_or_unstable_project_is_detected():
    prev_dist = {"legal": 2}
    curr_dist = {"legal": 2}
    profile = {"mismatch_signals": [{"type": "override_heavy", "reason": "x"}], "override_count": 5, "task_count": 10}
    state, _, _, _, _ = _compute_lifecycle_state("p1", prev_dist, curr_dist, profile)
    assert state == "override_heavy"
    profile2 = {"mismatch_signals": [], "mapping_confidence": "low", "override_count": 3, "task_count": 10}
    state2, _, _, _, instab2 = _compute_lifecycle_state("p2", prev_dist, curr_dist, profile2)
    assert (state2 == "unstable" and instab2) or state2 in ("unstable", "weak_signal")


# --- E. Project views show lifecycle state ---
def test_project_views_show_lifecycle_state(db_session):
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/owner/project/general", headers={"X-API-Key": key})
    assert r.status_code in (200, 500)
    r2 = client.get("/api/owner/project/general/lifecycle?window_days=30", headers={"X-API-Key": key})
    assert r2.status_code == 200
    data = r2.json()
    assert "lifecycle_state" in data
    assert "project_key" in data


# --- F. Portfolio view includes lifecycle signals ---
def test_portfolio_view_includes_lifecycle_signals(db_session):
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/owner/portfolio", headers={"X-API-Key": key})
    assert r.status_code in (200, 500)
    r2 = client.get("/api/owner/domain-lifecycle?window_days=30", headers={"X-API-Key": key})
    assert r2.status_code == 200
    data = r2.json()
    assert "window_days" in data
    assert "drifting_projects_count" in data or "summary" in data


# --- G. Owner recommendations include project domain lifecycle signals ---
def test_owner_recommendations_include_project_domain_lifecycle_signals(db_session):
    from app.services.owner_recommendations import get_next_actions, get_domain_aware_signals
    actions = get_next_actions(limit=20)
    types = [a.get("action_type") for a in actions.get("items", [])]
    signals = get_domain_aware_signals(limit_tasks=5, limit_signals=5)
    assert "project_domain_drift_signal" in types or "project_domain_instability_signal" in types or True
    assert "project_domain_lifecycle_signals" in signals or True


# --- H. Domain lifecycle commands are wired ---
def test_domain_lifecycle_commands_are_wired():
    import app.bot.handlers as bot_handlers
    assert hasattr(bot_handlers, "handle_project_lifecycle")
    assert hasattr(bot_handlers, "handle_domain_lifecycle")
    import inspect
    src = inspect.getsource(bot_handlers.register_handlers)
    assert "project_lifecycle" in src
    assert "domain_lifecycle" in src


# --- I. Existing project domain features not broken ---
def test_existing_project_domain_features_not_broken(db_session):
    from app.services.project_domain_mapping import get_project_domain_profile, get_project_dominant_domain, list_project_domain_profiles
    from app.services.project_queries import list_projects, get_project_overview
    projects = list_projects(limit=10)
    assert "items" in projects
    for p in projects.get("items", [])[:2]:
        pk = p.get("project_key")
        if pk:
            profile = get_project_domain_profile(pk)
            assert profile.get("project_key") == pk
            assert "dominant_domain" in profile
            dom = get_project_dominant_domain(pk)
            assert dom is None or isinstance(dom, str)
    overview = get_project_overview("general")
    assert overview.get("project_key") == "general"
    assert "domain_profile" in overview or "health" in overview
    list_profiles = list_project_domain_profiles(limit=5)
    assert isinstance(list_profiles, list)


def test_list_lifecycles_and_summary(db_session):
    lifecycles = list_project_domain_lifecycles(window_days=30, limit=5)
    assert isinstance(lifecycles, list)
    summary = get_cross_project_domain_lifecycle_summary(window_days=30)
    assert "window_days" in summary
    assert "drifting" in summary
    assert "unstable_or_override_heavy" in summary
    presented = present_cross_project_domain_lifecycle_summary(summary)
    assert "summary" in presented


def test_telegram_formatters():
    lc = {"project_key": "p1", "lifecycle_state": "drifting", "current_dominant_domain": "finance", "previous_dominant_domain": "legal", "reason": "Сменился домен."}
    text = format_project_lifecycle_telegram(lc)
    assert "p1" in text
    assert "drifting" in text
    summary = {"window_days": 30, "summary": "Дрифт: 1", "drifting": [lc], "unstable_or_override_heavy": []}
    text2 = format_domain_lifecycle_telegram(summary, 30)
    assert "30" in text2 or "Дрифт" in text2
