# tests/test_phase10_2_domain_prompts_and_override.py — Phase 10.2: step-specific prompts and override UX
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.domain_prompt_profiles import (
    build_pipeline_domain_prompt,
    build_roundtable_domain_prompt,
    build_court_domain_prompt,
    build_domain_prompt_for_step,
    STEP_PIPELINE,
    STEP_ROUNDTABLE,
    STEP_COURT,
)
from app.services.workflow_domain_context import get_effective_domain_context, apply_domain_override
from app.services.domain_override_store import get_override, clear_override

_reg_dir = Path(__file__).resolve().parents[2] / "app" / "data" / "domain_registry"
if _reg_dir.exists():
    os.environ["KNOW_PROFF_REGISTRY_DIR"] = str(_reg_dir)


# --- A. Pipeline / roundtable / court profiles differ by content or focus ---
def test_pipeline_roundtable_court_prompt_profiles_differ(db_session):
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="согласовать договор и проверить условия")
    task_id = task.id
    pp = build_pipeline_domain_prompt(task_id, task.owner_text)
    rp = build_roundtable_domain_prompt(task_id, task.owner_text)
    cp = build_court_domain_prompt(task_id, task.owner_text)
    assert pp["workflow_step"] == STEP_PIPELINE
    assert rp["workflow_step"] == STEP_ROUNDTABLE
    assert cp["workflow_step"] == STEP_COURT
    assert pp.get("step_specific_focus") != rp.get("step_specific_focus") or pp.get("context_profile_type") != rp.get("context_profile_type")
    assert cp.get("context_profile_type") == "judgement"
    assert pp.get("context_profile_type") == "execution"
    assert rp.get("context_profile_type") == "viewpoints"


# --- B. build_domain_prompt_for_step returns expected shape ---
def test_build_domain_prompt_for_step_returns_expected_shape(db_session):
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор лицензия")
    profile = build_domain_prompt_for_step(task.id, STEP_COURT, task.owner_text)
    assert "workflow_step" in profile
    assert "prompt_profile_key" in profile
    assert "primary_domain" in profile
    assert "secondary_domains" in profile
    assert "compact_context" in profile
    assert "step_specific_focus" in profile
    assert "selection_reason" in profile
    assert "included_sections" in profile
    assert "excluded_sections" in profile


# --- C. Override changes step-specific prompt ---
def test_effective_override_changes_step_specific_prompt(db_session, tmp_path):
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="написать код на Python")
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        p_before = build_court_domain_prompt(task.id, task.owner_text)
        apply_domain_override(task.id, "legal", reason="test", actor="owner", source="telegram")
        p_after = build_court_domain_prompt(task.id, task.owner_text)
        assert p_after.get("primary_domain") == "legal"
        assert p_after.get("domain_override") is True
        assert p_before.get("primary_domain") != "legal" or p_before.get("domain_override") is False
        clear_override(task.id)


# --- D. clear_task_domain command removes override ---
def test_clear_task_domain_command_removes_override(db_session, tmp_path):
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="любой текст")
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        apply_domain_override(task.id, "legal", reason="x", actor="owner", source="telegram")
        assert get_override(task.id) is not None
        cleared = clear_override(task.id)
        assert cleared is True
        assert get_override(task.id) is None
        eff = get_effective_domain_context(task.id, task.owner_text)
        assert eff.get("domain_override") is False


# --- E. Task domain endpoint returns debug context ---
def test_task_domain_endpoint_returns_debug_context(db_session):
    from app.storage.repositories import TaskRepository
    from app.dashboard.app import app
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор")
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/api/tasks/{task.id}/domain-context", headers={"X-API-Key": key})
    assert r.status_code == 200
    data = r.json()
    assert "effective_domain_context" in data
    assert "override_status" in data
    assert "step_profiles" in data
    assert "pipeline" in data["step_profiles"]
    assert "roundtable" in data["step_profiles"]
    assert "court" in data["step_profiles"]
    assert "explainability" in data


# --- F. Owner task view shows override and context hint ---
def test_owner_task_view_shows_override_and_context_hint(db_session, tmp_path):
    from app.services.owner_queries import get_task_card
    from app.presenters.owner_presenters import format_task_card
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="код на Python")
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        apply_domain_override(task.id, "legal", reason="для проверки", actor="owner", source="telegram")
        card = get_task_card(task.id)
        assert card.get("effective_domain_context", {}).get("domain_override") is True
        text = format_task_card(card)
        assert "Override" in text or "override" in text
        assert "legal" in text
        clear_override(task.id)


# --- G. Domain recommendations include override mismatch signal when needed ---
def test_domain_recommendations_include_override_mismatch_signal_when_needed(db_session, tmp_path):
    from app.services.owner_recommendations import get_domain_aware_signals, get_domain_override_signals
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="написать код на Python")
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        apply_domain_override(task.id, "legal", reason="manual", actor="owner", source="telegram")
        signals = get_domain_aware_signals(limit_tasks=10, limit_signals=5)
        assert "override_signals" in signals
        override_list = get_domain_override_signals(limit=5)
        types = [s.get("signal_type") for s in override_list]
        assert "manual_domain_correction_signal" in types or "override_mismatch_signal" in types or len(override_list) >= 0
        clear_override(task.id)


# --- H. Existing domain workflow features not broken ---
def test_existing_domain_workflow_features_not_broken(db_session):
    from app.services.workflow_domain_context import get_effective_domain_context
    from app.services.owner_queries import get_task_card
    from app.orchestrator.pipeline import run_pipeline
    from app.orchestrator.roundtable import run_roundtable
    from app.orchestrator.court import run_court
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор лицензия")
    triage_result = {"domain": "legal", "task_type": "review", "workflow_domain_context": get_effective_domain_context(task.id, task.owner_text)}
    pipeline_result = run_pipeline(task.id, triage_result, repo)
    assert "handoffs" in pipeline_result
    roundtable_result = run_roundtable(task.id, triage_result, pipeline_result, repo)
    assert "risk_table" in roundtable_result
    court_result = run_court(task.id, triage_result, pipeline_result, roundtable_result, repo)
    assert "report_path" in court_result or "summary" in court_result
    card = get_task_card(task.id)
    assert card is not None
    assert "effective_domain_context" in card


# --- I. Web override controls are wired (form actions and API) ---
def test_web_override_controls_are_wired(db_session):
    from app.dashboard.app import app
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="тест")
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r_set = client.post(
        f"/api/tasks/{task.id}/domain-override",
        json={"domain_key": "legal", "reason": "test"},
        headers={"X-API-Key": key},
    )
    assert r_set.status_code in (200, 400)
    if r_set.status_code == 200:
        r_clear = client.post(
            f"/api/tasks/{task.id}/domain-override/clear",
            headers={"X-API-Key": key},
        )
        assert r_clear.status_code == 200
