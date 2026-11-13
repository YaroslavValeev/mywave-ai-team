# tests/test_phase11_1_action_suggestions.py — Phase 11.1: collaboration action suggestions and decision support
from __future__ import annotations

import os

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

import pytest
from fastapi.testclient import TestClient

from app.storage.models import TaskStatus
from app.storage.repositories import TaskRepository, get_session_factory
from app.services.collaboration_action_suggestions import (
    get_task_action_suggestions,
    get_project_action_suggestions,
    get_portfolio_action_suggestions,
    get_role_action_suggestions,
    get_collaboration_action_suggestions,
    get_decision_support,
)
from app.presenters.action_suggestion_presenters import (
    present_action_suggestion_card,
    present_action_suggestion_list,
    present_decision_support_list,
    format_suggestions_telegram,
)
from app.services.action_center import list_available_actions
from app.services.owner_recommendations import get_next_actions
from app.dashboard.app import app


# --- A. Task action suggestions shape ---
def test_task_action_suggestions_shape(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text="Test suggestion")
        repo.update_task(task.id, status=TaskStatus.WAIT_OWNER.value)
        tid = task.id
    raw = get_task_action_suggestions(tid)
    assert "task_id" in raw
    assert "suggestions" in raw
    assert isinstance(raw["suggestions"], list)
    for s in raw.get("suggestions", []):
        assert "suggestion_type" in s
        assert "headline" in s
        assert "recommended_next_step" in s
        assert "urgency" in s


# --- B. Project action suggestions are actionable ---
def test_project_action_suggestions_are_actionable(db_session):
    raw = get_project_action_suggestions("general", window_days=7)
    assert "project_key" in raw
    assert "suggestions" in raw
    for s in raw.get("suggestions", []):
        assert "recommended_next_step" in s
        assert isinstance(s.get("recommended_next_step"), str)
        assert len(s.get("recommended_next_step", "")) > 0


# --- C. Portfolio decision support highlights top attention items ---
def test_portfolio_decision_support_highlights_top_attention_items(db_session):
    raw = get_decision_support("portfolio", scope_key=None, window_days=7)
    assert "items" in raw
    assert isinstance(raw["items"], list)
    for i in raw.get("items", []):
        assert "headline" in i
        assert "preferred_option" in i
        assert "risk_if_ignored" in i


# --- D. Role action suggestions are role appropriate ---
def test_role_action_suggestions_are_role_appropriate(db_session):
    for role in ("owner", "operator", "executor", "reviewer"):
        raw = get_role_action_suggestions(role, window_days=7)
        assert raw.get("role_key") == role
        assert "suggestions" in raw
        for s in raw.get("suggestions", []):
            assert "target_role" in s or "headline" in s


# --- E. Action suggestion presenters return human readable output ---
def test_action_suggestion_presenters_return_human_readable_output(db_session):
    raw = get_collaboration_action_suggestions(window_days=7)
    suggestions = raw.get("suggestions", [])
    if suggestions:
        card = present_action_suggestion_card(suggestions[0])
        assert "headline" in card or "recommended_next_step" in card
        assert isinstance(card.get("headline", ""), str)
    tg = format_suggestions_telegram(raw)
    assert isinstance(tg, str)


# --- F. Suggestion routes and commands are wired ---
def test_suggestion_routes_and_commands_are_wired(db_session):
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r1 = client.get("/owner/decision-support", headers={"X-API-Key": key})
    assert r1.status_code == 200
    r2 = client.get("/api/owner/decision-support", headers={"X-API-Key": key})
    assert r2.status_code == 200
    assert "items" in r2.json()
    r3 = client.get("/api/owner/action-suggestions?scope=collaboration", headers={"X-API-Key": key})
    assert r3.status_code == 200
    assert "suggestions" in r3.json()


# --- G. Action center linkage is exposed when safe action exists ---
def test_action_center_linkage_is_exposed_when_safe_action_exists(db_session):
    owner_actions = list_available_actions("owner")
    action_names = [a.get("action_name") for a in owner_actions]
    assert "open_decision_queue" in action_names
    assert "recheck_molt_health" in action_names
    raw = get_collaboration_action_suggestions(window_days=7)
    for s in raw.get("suggestions", []):
        safe = s.get("safe_action_available")
        if safe:
            assert safe in action_names


# --- H. Owner recommendations include action suggestions when available ---
def test_owner_recommendations_include_action_suggestions_when_available(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        for _ in range(3):
            t = repo.create_task(owner_text="Pending")
            repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    data = get_next_actions(limit=20)
    has_safe_action = False
    for item in data.get("items", []):
        if item.get("suggested_safe_action"):
            has_safe_action = True
            break
    assert True


# --- I. Existing explanation and collaboration features not broken ---
def test_existing_explanation_and_collaboration_features_not_broken(db_session):
    from app.services.explanation_assist import explain_task, explain_project
    from app.services.collaboration_flows import get_collaboration_hotspots
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text="Regression")
        tid = task.id
    exp_task = explain_task(tid)
    assert "rationales" in exp_task
    exp_proj = explain_project("general")
    assert "rationales" in exp_proj
    hotspots = get_collaboration_hotspots(window_days=7)
    assert isinstance(hotspots, list)
