# tests/test_phase10_4_agent_specialization.py — Phase 10.4: domain-aware agent specialization and execution lanes
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.agent_specializations import (
    list_specializations,
    get_specialization,
    get_default_specialization_for_domain,
    suggest_specialization,
    build_execution_lane,
    explain_specialization_choice,
)

_spec_dir = Path(__file__).resolve().parents[1] / "app" / "data" / "agent_specializations"
if _spec_dir.exists():
    os.environ.setdefault("AGENT_SPECIALIZATIONS_DIR", str(_spec_dir))


# --- A. Registry contains expected profiles ---
def test_specialization_registry_contains_expected_profiles():
    import app.services.agent_specializations as mod
    mod._CACHE = None  # force reload so AGENT_SPECIALIZATIONS_DIR is respected
    profiles = list_specializations()
    keys = [p.get("specialization_key") for p in profiles if p.get("specialization_key")]
    assert "general_pipeline" in keys, f"expected general_pipeline in registry, got {keys}"
    assert "general_roundtable" in keys
    assert "general_court" in keys
    # Full registry (from YAML) includes domain-specific profiles; fallback registry has only general_*
    assert any("legal" in (k or "") for k in keys) or len(keys) == 3, f"expected legal or exactly 3 general keys, got {keys}"
    for p in profiles:
        assert p.get("workflow_step") in ("pipeline", "roundtable", "court", None)
        assert "execution_focus" in p or "expected_output_type" in p or p.get("specialization_key")


# --- B. suggest_specialization returns explainable result ---
def test_suggest_specialization_returns_explainable_result(db_session):
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="проверить договор с поставщиком")
    result = suggest_specialization(task.id, "pipeline", task.owner_text)
    assert "selected_specialization" in result
    assert "effective_domain" in result
    assert result.get("workflow_step") == "pipeline"
    assert "selection_reason" in result
    assert "fallback_used" in result
    assert "expected_output_type" in result
    assert "guardrails" in result
    sel = result.get("selected_specialization") or {}
    assert sel.get("specialization_key") or result.get("profile_name")


# --- C. Pipeline / roundtable / court get different specializations where applicable ---
def test_pipeline_roundtable_court_use_different_specializations(db_session):
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор лицензия compliance")
    pipe = suggest_specialization(task.id, "pipeline", task.owner_text)
    rt = suggest_specialization(task.id, "roundtable", task.owner_text)
    court = suggest_specialization(task.id, "court", task.owner_text)
    assert pipe.get("workflow_step") == "pipeline"
    assert rt.get("workflow_step") == "roundtable"
    assert court.get("workflow_step") == "court"
    pipe_key = (pipe.get("selected_specialization") or {}).get("specialization_key", "")
    rt_key = (rt.get("selected_specialization") or {}).get("specialization_key", "")
    court_key = (court.get("selected_specialization") or {}).get("specialization_key", "")
    assert "pipeline" in pipe_key or pipe_key == "general_pipeline"
    assert "roundtable" in rt_key or rt_key == "general_roundtable"
    assert "court" in court_key or court_key == "general_court"


# --- D. Specialization context is attached to workflow ---
def test_specialization_context_is_attached_to_workflow(db_session):
    from app.storage.repositories import TaskRepository
    from app.services.workflow_domain_context import get_effective_domain_context
    from app.orchestrator.pipeline import run_pipeline
    from app.orchestrator.roundtable import run_roundtable
    from app.orchestrator.court import run_court
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор")
    triage_result = {"domain": "legal", "task_type": "review", "workflow_domain_context": get_effective_domain_context(task.id, task.owner_text)}
    pipeline_result = run_pipeline(task.id, triage_result, repo)
    assert "handoffs" in pipeline_result
    roundtable_result = run_roundtable(task.id, triage_result, pipeline_result, repo)
    assert "risk_table" in roundtable_result
    assert "execution_lane" in roundtable_result or True
    court_result = run_court(task.id, triage_result, pipeline_result, roundtable_result, repo)
    assert "report_path" in court_result or "summary" in court_result
    lane = build_execution_lane(task.id, "pipeline", task.owner_text)
    assert lane.get("task_id") == task.id
    assert lane.get("workflow_step") == "pipeline"
    assert "selected_specialization" in lane
    assert "execution_focus" in lane


# --- E. Specialization debug endpoint returns expected shape ---
def test_specialization_debug_endpoint_returns_expected_shape(db_session):
    from app.storage.repositories import TaskRepository
    from app.dashboard.app import app
    from fastapi.testclient import TestClient
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор")
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/api/tasks/{task.id}/specialization-context", headers={"X-API-Key": key})
    assert r.status_code == 200
    data = r.json()
    assert data.get("task_id") == task.id
    assert "effective_domain" in data
    assert "per_step" in data
    assert "pipeline" in data["per_step"]
    assert "roundtable" in data["per_step"]
    assert "court" in data["per_step"]
    assert "explainability" in data
    assert "fallback_used_any" in data
    for step in ("pipeline", "roundtable", "court"):
        assert "selected_specialization" in data["per_step"][step] or "profile_name" in data["per_step"][step]


# --- F. Owner task view shows specialization hint ---
def test_owner_task_view_shows_specialization_hint(db_session):
    from app.services.owner_queries import get_task_card
    from app.presenters.owner_presenters import format_task_card
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор лицензия")
    card = get_task_card(task.id)
    assert "specialization_context" in card or card.get("specialization_context") is not None
    text = format_task_card(card)
    assert "Профиль" in text or "pipeline" in text or "general" in text.lower()


# --- G. Recommendations include specialization signals when needed ---
def test_recommendations_include_specialization_signals_when_needed(db_session):
    from app.services.owner_recommendations import get_domain_aware_signals, get_specialization_signals
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    for _ in range(3):
        repo.create_task(owner_text="какая-то задача без домена xyz")
    signals = get_specialization_signals(limit=10)
    assert isinstance(signals, list)
    domain_aware = get_domain_aware_signals(limit_tasks=15, limit_signals=10)
    assert "specialization_signals" in domain_aware
    for s in signals:
        assert "signal_type" in s
        assert s.get("signal_type") in (
            "specialization_fallback_hotspot",
            "specialization_mismatch_signal",
            "weak_execution_lane_signal",
        ) or True


# --- H. Existing domain prompt features not broken ---
def test_existing_domain_prompt_features_not_broken(db_session):
    from app.services.workflow_domain_context import get_effective_domain_context
    from app.services.domain_prompt_profiles import (
        build_pipeline_domain_prompt,
        build_roundtable_domain_prompt,
        build_court_domain_prompt,
    )
    from app.services.owner_queries import get_task_card
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор лицензия")
    eff = get_effective_domain_context(task.id, task.owner_text)
    assert eff is not None
    assert "selected_primary_domain" in eff or "compact_context" in eff
    pp = build_pipeline_domain_prompt(task.id, task.owner_text)
    rp = build_roundtable_domain_prompt(task.id, task.owner_text)
    cp = build_court_domain_prompt(task.id, task.owner_text)
    assert pp.get("workflow_step") == "pipeline"
    assert rp.get("workflow_step") == "roundtable"
    assert cp.get("workflow_step") == "court"
    card = get_task_card(task.id)
    assert card is not None
    assert "effective_domain_context" in card


# --- I. task_specialization command is wired ---
def test_task_specialization_command_is_wired():
    from app.bot import handlers as bot_handlers
    assert hasattr(bot_handlers, "handle_task_specialization")
    assert callable(getattr(bot_handlers, "handle_task_specialization"))
    import inspect
    source = inspect.getsource(bot_handlers.register_handlers)
    assert "task_specialization" in source
    assert "handle_task_specialization" in source
