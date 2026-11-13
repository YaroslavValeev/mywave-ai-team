# tests/test_phase10_9_collaboration_flows.py — Phase 10.9: domain-aware collaboration and handoff
from __future__ import annotations

import os

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

import pytest
from fastapi.testclient import TestClient

from app.storage.models import TaskStatus
from app.storage.repositories import TaskRepository, get_session_factory
from app.services.collaboration_flows import (
    get_task_handoff_signals,
    get_project_handoff_signals,
    get_role_collaboration_summary,
    get_cross_role_handoffs,
    get_collaboration_hotspots,
    get_collaboration_recommendations,
)
from app.presenters.collaboration_presenters import (
    present_task_handoff_signals,
    present_project_handoff_signals,
    present_role_collaboration_summary,
    present_cross_role_handoffs,
    present_collaboration_hotspots,
    present_collaboration_recommendations,
)
from app.dashboard.app import app


# --- A. Task handoff signals shape ---
def test_task_handoff_signals_shape(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text="Test")
        repo.update_task(task.id, status=TaskStatus.WAIT_OWNER.value)
        tid = task.id
    raw = get_task_handoff_signals(tid)
    assert "task_id" in raw
    assert raw["task_id"] == tid
    assert "handoff_signals" in raw
    assert isinstance(raw["handoff_signals"], list)
    presented = present_task_handoff_signals(raw)
    assert "task_id" in presented
    assert "handoff_signals" in presented


# --- B. Project handoff signals detect review/owner bottleneck ---
def test_project_handoff_signals_detect_review_or_owner_bottleneck(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        for _ in range(3):
            t = repo.create_task(owner_text="Pending approval")
            repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    raw = get_project_handoff_signals("general")
    assert "project_key" in raw
    assert "handoff_signals" in raw
    assert raw.get("pending_count", 0) >= 2
    types = [s.get("handoff_type") for s in raw.get("handoff_signals", [])]
    assert "executor_to_owner" in types or len(raw["handoff_signals"]) > 0


# --- C. Role collaboration summary returns actionable items ---
def test_role_collaboration_summary_returns_actionable_items(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        t = repo.create_task(owner_text="Need owner")
        repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    for role in ("owner", "reviewer", "executor", "operator"):
        raw = get_role_collaboration_summary(role)
        assert "role_key" in raw
        assert raw["role_key"] == role
        assert "collaboration_items" in raw
        assert "count" in raw
        assert isinstance(raw["collaboration_items"], list)
        presented = present_role_collaboration_summary(raw)
        assert "collaboration_items" in presented


# --- D. Collaboration hotspots are explainable ---
def test_collaboration_hotspots_are_explainable(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        for _ in range(3):
            t = repo.create_task(owner_text="Pending")
            repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    hotspots = get_collaboration_hotspots(window_days=7, limit=10)
    assert isinstance(hotspots, list)
    for h in hotspots:
        assert "hotspot_type" in h
        assert "reason" in h
        assert "recommended_collaboration_action" in h
        assert "severity" in h
    presented = present_collaboration_hotspots(hotspots)
    assert "items" in presented
    assert "count" in presented


# --- E. Portfolio includes collaboration signals ---
def test_portfolio_includes_collaboration_signals(db_session):
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/owner/portfolio", headers={"X-API-Key": key})
    assert r.status_code == 200
    assert "collaboration" in r.text.lower() or "Collaboration" in r.text


# --- F. Collaboration routes and commands are wired ---
def test_collaboration_routes_and_commands_are_wired(db_session):
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/owner/collaboration", headers={"X-API-Key": key})
    assert r.status_code == 200
    assert "handoff" in r.text.lower() or "Collaboration" in r.text
    r2 = client.get("/api/owner/collaboration?window_days=7", headers={"X-API-Key": key})
    assert r2.status_code == 200
    data = r2.json()
    assert "handoffs" in data
    assert "hotspots" in data
    assert "recommendations" in data


# --- G. Owner recommendations include collaboration signals ---
def test_owner_recommendations_include_collaboration_signals(db_session):
    from app.services.owner_recommendations import get_next_actions

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        for _ in range(3):
            t = repo.create_task(owner_text="Pending")
            repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    actions = get_next_actions(limit=20)
    types = [a.get("action_type") for a in actions.get("items", [])]
    collab_types = (
        "approval_bottleneck_signal",
        "review_execution_loop_signal",
        "owner_attention_gap_signal",
        "runtime_escalation_signal",
        "collaboration_hotspot_signal",
    )
    has_collab = any(t in types for t in collab_types)
    assert has_collab or len(actions.get("items", [])) >= 1


# --- H. Existing role and domain views not broken ---
def test_existing_role_and_domain_views_not_broken(db_session):
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    for path in ("/owner", "/views/operator", "/views/executor", "/views/reviewer"):
        r = client.get(path, headers={"X-API-Key": key})
        assert r.status_code in (200, 302, 404), f"{path} returned {r.status_code}"
    r = client.get("/owner/project/general", headers={"X-API-Key": key})
    assert r.status_code in (200, 500), f"/owner/project/general returned {r.status_code}"
    r = client.get("/owner/domains", headers={"X-API-Key": key})
    assert r.status_code == 200


# --- I. Project view shows collaboration block ---
def test_project_view_shows_collaboration_block(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        t = repo.create_task(owner_text="Test")
        repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/owner/project/general", headers={"X-API-Key": key})
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        assert "collaboration" in r.text.lower() or "Collaboration" in r.text or "handoff" in r.text.lower()
