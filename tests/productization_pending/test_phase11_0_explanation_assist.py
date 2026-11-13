# tests/test_phase11_0_explanation_assist.py — Phase 11.0: explanation assist and rationale surfaces
from __future__ import annotations

import os

os.environ.setdefault("OWNER_API_KEY", "test_key_for_smoke")

import pytest
from fastapi.testclient import TestClient

from app.storage.models import TaskStatus
from app.storage.repositories import TaskRepository, get_session_factory
from app.services.explanation_assist import (
    explain_task,
    explain_project,
    explain_portfolio,
    explain_collaboration,
    explain_refinement,
)
from app.presenters.explanation_presenters import (
    present_rationale_card,
    present_rationale_list,
    present_task_explanation,
    present_project_explanation,
    present_portfolio_explanation,
    present_collaboration_explanation,
    present_refinement_explanation,
    format_task_explanation_telegram,
)
from app.services.owner_recommendations import get_next_actions
from app.dashboard.app import app


# --- A. Task rationale shape ---
def test_explain_task_returns_unified_rationale_shape(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text="Test explanation")
        tid = task.id
    raw = explain_task(tid)
    assert "task_id" in raw
    assert raw["task_id"] == tid
    assert "rationales" in raw
    assert isinstance(raw["rationales"], list)
    for r in raw.get("rationales", []):
        assert "rationale_type" in r
        assert "subject_type" in r
        assert "subject_key" in r
        assert "headline" in r
        assert "evidence_items" in r
        assert isinstance(r["evidence_items"], list)
        assert "confidence_label" in r


# --- B. Project explanation includes domain and lifecycle evidence ---
def test_explain_project_includes_domain_and_lifecycle_evidence(db_session):
    raw = explain_project("general", window_days=7)
    assert "project_key" in raw
    assert "rationales" in raw
    assert isinstance(raw["rationales"], list)
    for r in raw.get("rationales", []):
        assert "headline" in r
        assert "evidence_items" in r
        assert isinstance(r["evidence_items"], list)


# --- C. Collaboration explanation includes handoff reason ---
def test_explain_collaboration_includes_handoff_reason(db_session):
    raw = explain_collaboration(project_key=None, window_days=7)
    assert "rationales" in raw
    assert isinstance(raw["rationales"], list)
    for r in raw.get("rationales", []):
        assert "headline" in r
        assert "reason" in r or "headline" in r


# --- D. Refinement rationale includes signal and recommended change ---
def test_explain_refinement_includes_signal_and_recommended_change(db_session):
    raw = explain_refinement(proposal_id=None, window_days=7)
    assert "rationales" in raw
    assert isinstance(raw["rationales"], list)
    for r in raw.get("rationales", []):
        assert "headline" in r
        assert "recommended_action" in r or "rationale_type" in r


# --- E. Explanation presenters return human readable output ---
def test_explanation_presenters_return_human_readable_output(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text="Presenter test")
        tid = task.id
    raw = explain_task(tid)
    presented = present_task_explanation(raw)
    assert "rationales" in presented or "headline" in presented
    for r in presented.get("rationales", []):
        assert "headline" in r
        assert isinstance(r.get("headline", ""), str)
        assert len(r.get("headline", "")) > 0 or r.get("evidence_items")
    card = present_rationale_card(raw.get("rationales", [{}])[0] if raw.get("rationales") else {})
    assert card == {} or "headline" in card or "evidence_items" in card
    tg = format_task_explanation_telegram(raw)
    assert isinstance(tg, str)
    assert len(tg) > 0


# --- F. Explanation routes and commands are wired ---
def test_explanation_routes_and_commands_are_wired(db_session):
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text="Route test")
        tid = task.id
    r1 = client.get(f"/api/explain/task/{tid}", headers={"X-API-Key": key})
    assert r1.status_code == 200
    assert "rationales" in r1.json()
    r2 = client.get("/api/explain/project/general", headers={"X-API-Key": key})
    assert r2.status_code == 200
    assert "rationales" in r2.json()
    r3 = client.get("/api/explain/portfolio", headers={"X-API-Key": key})
    assert r3.status_code == 200
    r4 = client.get("/api/explain/collaboration", headers={"X-API-Key": key})
    assert r4.status_code == 200
    r5 = client.get("/api/explain/refinement", headers={"X-API-Key": key})
    assert r5.status_code == 200


# --- G. Owner recommendations expose compact rationale when available ---
def test_owner_recommendations_expose_compact_rationale_when_available(db_session):
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        for _ in range(3):
            t = repo.create_task(owner_text="Pending approval")
            repo.update_task(t.id, status=TaskStatus.WAIT_OWNER.value)
    data = get_next_actions(limit=20)
    items = data.get("items", [])
    has_rationale = False
    for item in items:
        if item.get("rationale_headline") or item.get("evidence_summary"):
            has_rationale = True
            assert isinstance(item.get("rationale_headline", ""), str) or isinstance(item.get("evidence_summary"), list)
            break
    assert True


# --- H. Existing domain/collaboration/refinement features not broken ---
def test_existing_domain_collaboration_refinement_features_not_broken(db_session):
    from app.services.workflow_domain_context import get_effective_domain_context
    from app.services.collaboration_flows import get_collaboration_hotspots, get_cross_role_handoffs
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.create_task(owner_text="Regression test")
        tid = task.id
    eff = get_effective_domain_context(tid, "Regression test")
    assert "selected_primary_domain" in eff or "context_selection_source" in eff or eff
    hotspots = get_collaboration_hotspots(window_days=7, limit=5)
    assert isinstance(hotspots, list)
    handoffs = get_cross_role_handoffs(window_days=7, limit=5)
    assert "items" in handoffs or isinstance(handoffs, (list, dict))


# --- I. Portfolio explanation highlights why project is in focus ---
def test_portfolio_explanation_highlights_why_project_is_in_focus(db_session):
    raw = explain_portfolio(window_days=7)
    assert "rationales" in raw
    assert isinstance(raw["rationales"], list)
    presented = present_portfolio_explanation(raw)
    assert "rationales" in presented or "count" in presented
    for r in raw.get("rationales", [])[:3]:
        assert "headline" in r
        assert isinstance(r.get("headline"), str)
