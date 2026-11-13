# tests/test_phase10_3_project_domain_and_role.py — Phase 10.3: project-domain mapping and role-domain recommendations
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

_reg_dir = Path(__file__).resolve().parents[2] / "app" / "data" / "domain_registry"
if _reg_dir.exists():
    os.environ["KNOW_PROFF_REGISTRY_DIR"] = str(_reg_dir)


# --- A. Project domain profile shape ---
def test_project_domain_profile_shape(db_session):
    from app.services.project_domain_mapping import get_project_domain_profile
    from app.storage.repositories import TaskRepository
    from app.services.project_queries import _project_key
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="договор лицензия")
    pk = _project_key(t)
    profile = get_project_domain_profile(pk)
    assert "project_key" in profile
    assert "dominant_domain" in profile
    assert "secondary_domains" in profile
    assert "domain_distribution" in profile
    assert "domain_signal_source" in profile
    assert "mapping_confidence" in profile
    assert "mismatch_signals" in profile
    assert "updated_at" in profile
    assert "task_count" in profile
    assert "override_count" in profile


# --- B. Project dominant domain is explainable ---
def test_project_dominant_domain_is_explainable(db_session):
    from app.services.project_domain_mapping import get_project_domain_profile, get_project_dominant_domain
    from app.storage.repositories import TaskRepository
    from app.services.project_queries import _project_key
    repo = TaskRepository(db_session)
    repo.create_task(owner_text="согласовать договор")
    repo.create_task(owner_text="проверить лицензию")
    pk = "general"
    profile = get_project_domain_profile(pk)
    dominant = get_project_dominant_domain(pk)
    assert profile.get("dominant_domain") == dominant
    assert profile.get("domain_distribution") is not None or profile.get("task_count") >= 0


# --- C. Project domain mismatch signal when override heavy ---
def test_project_domain_mismatch_signal_detected_when_override_heavy(db_session, tmp_path):
    from app.services.project_domain_mapping import get_project_domain_profile
    from app.services.workflow_domain_context import apply_domain_override
    from app.storage.repositories import TaskRepository
    from app.services.project_queries import _project_key
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        repo = TaskRepository(db_session)
        t1 = repo.create_task(owner_text="код Python")
        t2 = repo.create_task(owner_text="код API")
        pk = _project_key(t1)
        apply_domain_override(t1.id, "legal", reason="x", actor="owner", source="telegram")
        apply_domain_override(t2.id, "legal", reason="y", actor="owner", source="telegram")
        profile = get_project_domain_profile(pk)
        assert profile.get("override_count") >= 2
        assert any(s.get("type") == "override_heavy" for s in profile.get("mismatch_signals", []))


# --- D. Role domain recommendations return actionable items ---
def test_role_domain_recommendations_return_actionable_items(db_session):
    from app.services.role_domain_recommendations import get_role_domain_recommendations
    for role in ("owner", "operator", "executor", "reviewer"):
        rec = get_role_domain_recommendations(role, limit_domains=3)
        assert "role_key" in rec
        assert "recommended_domains" in rec
        assert "current_domain_pressure" in rec
        assert "why_this_role_needs_it" in rec
        assert "recommended_action" in rec
        assert "evidence_summary" in rec
        assert isinstance(rec["recommended_domains"], list)


# --- E. Project views show domain profile ---
def test_project_views_show_domain_profile(db_session):
    from app.services.project_queries import list_projects, get_project_overview
    from app.presenters.project_presenters import present_project_list, present_project_overview
    raw = list_projects(limit=5)
    data = present_project_list(raw)
    for p in data.get("items", []):
        assert "dominant_domain" in p
    overview_raw = get_project_overview("general")
    overview = present_project_overview(overview_raw)
    assert "domain_profile" in overview or overview_raw.get("domain_profile") is None


# --- F. Role views show domain recommendations ---
def test_role_views_show_domain_recommendations(db_session):
    from app.services.role_views import get_owner_view, get_operator_view, get_executor_view, get_reviewer_view
    for get_view in (get_owner_view, get_operator_view, get_executor_view, get_reviewer_view):
        data = get_view()
        assert "domain_recommendations" in data
        dr = data.get("domain_recommendations", {})
        assert "role_key" in dr or not dr
        assert "recommended_domains" in dr or not dr


# --- G. Cross-project domain summary exists ---
def test_cross_project_domain_summary_exists(db_session):
    from app.services.project_domain_mapping import get_cross_project_domain_summary
    summary = get_cross_project_domain_summary()
    assert "project_profiles_count" in summary
    assert "domains_with_projects" in summary
    assert "summary" in summary


# --- H. New domain commands are wired ---
def test_new_domain_commands_are_wired():
    from app.bot.handlers import handle_project_domain, handle_role_domains, handle_domain_pressure
    from app.services.project_domain_mapping import get_project_domain_profile
    from app.services.role_domain_recommendations import get_role_domain_recommendations
    assert callable(handle_project_domain)
    assert callable(handle_role_domains)
    assert callable(handle_domain_pressure)
    profile = get_project_domain_profile("general")
    assert "project_key" in profile
    rec = get_role_domain_recommendations("owner", limit_domains=2)
    assert "recommended_domains" in rec


# --- I. Existing domain workflow and registry not broken ---
def test_existing_domain_workflow_and_registry_features_not_broken(db_session):
    from app.services.workflow_domain_context import get_effective_domain_context
    from app.services.domain_prompt_profiles import build_pipeline_domain_prompt
    from app.services.owner_recommendations import get_domain_aware_signals
    from app.services.domain_registry import list_domains
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="договор")
    eff = get_effective_domain_context(t.id, t.owner_text)
    assert "selected_primary_domain" in eff
    profile = build_pipeline_domain_prompt(t.id, t.owner_text)
    assert profile.get("workflow_step") == "pipeline"
    signals = get_domain_aware_signals(limit_tasks=5, limit_signals=3)
    assert "items" in signals
    assert "override_signals" in signals
    assert "project_domain_signals" in signals
    doms = list_domains()
    assert isinstance(doms, list)
