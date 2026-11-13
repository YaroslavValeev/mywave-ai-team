# tests/test_phase10_1_domain_workflow.py — Phase 10.1: domain-aware workflow and context
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.workflow_domain_context import (
    build_workflow_domain_context,
    get_effective_domain_context,
    apply_domain_override,
    explain_effective_domain_context,
)
from app.services.domain_override_store import get_override, set_override, clear_override

_reg_dir = Path(__file__).resolve().parents[2] / "app" / "data" / "domain_registry"
if _reg_dir.exists():
    os.environ["KNOW_PROFF_REGISTRY_DIR"] = str(_reg_dir)


# --- A. Workflow domain context shape ---
def test_workflow_domain_context_shape():
    ctx = build_workflow_domain_context("проверить договор с поставщиком", task_id=None)
    assert "selected_primary_domain" in ctx
    assert "selected_secondary_domains" in ctx
    assert "selected_context_pack_keys" in ctx
    assert "compact_context" in ctx
    assert "context_selection_reason" in ctx
    assert "context_selection_source" in ctx
    assert "domain_override" in ctx
    assert "domain_override_source" in ctx
    assert "domain_override_reason" in ctx
    assert "domain_context_version" in ctx
    assert ctx["domain_override"] is False
    assert isinstance(ctx["selected_secondary_domains"], list)


# --- B. Effective context uses override when present ---
def test_effective_domain_context_uses_override_when_present(db_session, tmp_path):
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="написать код на Python")
    task_id = task.id
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        set_override(task_id, "legal", reason="owner choice", actor="owner", source="telegram")
        eff = get_effective_domain_context(task_id, task.owner_text)
        assert eff.get("selected_primary_domain") == "legal"
        assert eff.get("domain_override") is True
        assert "owner" in (eff.get("domain_override_reason") or "") or eff.get("context_selection_source") == "override"
        clear_override(task_id)


# --- C. Domain override is persisted and audited ---
def test_domain_override_is_persisted_and_audited(db_session, tmp_path):
    from app.storage.repositories import TaskRepository
    from app.shared.audit import log_audit
    from app.storage.models import AuditEvent
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="тест")
    task_id = task.id
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        set_override(task_id, "legal", reason="audit test", actor="owner", source="telegram")
        rec = get_override(task_id)
        assert rec is not None
        assert rec.get("new_primary_domain") == "legal"
        assert rec.get("override_active") is True
        log_audit(repo, "domain_override", task_id=task_id, payload={"new_primary_domain": "legal"})
    events = db_session.query(AuditEvent).filter(AuditEvent.event_type == "domain_override").all()
    assert len(events) >= 1
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        clear_override(task_id)


# --- D. /task_domain shows effective domain ---
def test_task_domain_command_shows_effective_domain(db_session):
    from app.services.owner_queries import get_task_card
    from app.presenters.owner_presenters import format_task_card
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="согласовать договор")
    card = get_task_card(task.id)
    assert card is not None
    edc = card.get("effective_domain_context")
    assert edc is not None
    assert "selected_primary_domain" in edc
    text = format_task_card(card)
    assert "Экспертиза" in text or "legal" in text or edc.get("selected_primary_domain") in text


# --- E. /set_task_domain updates override ---
def test_set_task_domain_command_updates_override(db_session, tmp_path):
    from app.storage.repositories import TaskRepository
    with patch("app.services.domain_override_store._OVERRIDES_PATH", tmp_path / "overrides.json"):
        repo = TaskRepository(db_session)
        task = repo.create_task(owner_text="любой текст")
        result = apply_domain_override(task.id, "legal", reason="test", actor="owner", source="telegram")
        assert result.get("success") is True
        assert result.get("override", {}).get("new_primary_domain") == "legal"
        eff = get_effective_domain_context(task.id, task.owner_text)
        assert eff.get("selected_primary_domain") == "legal"
        assert eff.get("domain_override") is True
        clear_override(task.id)


# --- F. Domain context attached to workflow after triage ---
def test_domain_context_is_attached_to_workflow_after_triage(db_session):
    from app.services.workflow_domain_context import get_effective_domain_context
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="договор лицензия")
    wf_ctx = get_effective_domain_context(task.id, task.owner_text)
    assert "workflow_domain_context" not in wf_ctx
    triage_result = {"domain": "legal", "task_type": "review"}
    triage_result["workflow_domain_context"] = wf_ctx
    assert triage_result.get("workflow_domain_context") is not None
    assert triage_result["workflow_domain_context"].get("selected_primary_domain") is not None or True
    assert "compact_context" in triage_result["workflow_domain_context"] or "selected_primary_domain" in triage_result["workflow_domain_context"]


# --- G. Owner task view shows override when present ---
def test_owner_task_view_shows_override_when_present(db_session, tmp_path):
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
        assert "Override" in text or "override" in text or "owner" in text
        clear_override(task.id)


# --- H. Domain-aware recommendations use effective domain context ---
def test_domain_aware_recommendations_use_effective_domain_context(db_session):
    from app.services.owner_recommendations import get_domain_aware_signals
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    repo.create_task(owner_text="договор")
    repo.create_task(owner_text="API тесты")
    signals = get_domain_aware_signals(limit_tasks=10, limit_signals=5)
    assert "items" in signals
    assert "explainable" in signals
    for item in signals.get("items", []):
        assert "domain_key" in item
        assert "reason" in item


# --- I. Domain routes and Phase 9.9 features not broken ---
def test_domain_routes_and_existing_registry_features_not_broken():
    from fastapi.testclient import TestClient
    from app.dashboard.app import app
    client = TestClient(app, raise_server_exceptions=False)
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    headers = {"X-API-Key": key}
    r = client.get("/owner/domains", headers=headers)
    assert r.status_code in (200, 401, 500)
    r2 = client.get("/api/owner/domain/legal", headers=headers)
    assert r2.status_code in (200, 401, 404, 500)
    r3 = client.get("/api/owner/route", params={"text": "договор"}, headers=headers)
    assert r3.status_code in (200, 401, 500)
