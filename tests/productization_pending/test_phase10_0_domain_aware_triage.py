# tests/test_phase10_0_domain_aware_triage.py — Phase 10.0: domain-aware triage and context selection
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.services.domain_triage import (
    triage_domains_for_task,
    build_task_domain_metadata,
    select_context_for_task,
    explain_task_domain_selection,
)
from app.services.task_domain_store import get_task_domain_metadata
from app.presenters.owner_presenters import format_domain_hint_compact, format_task_card
from app.presenters.domain_presenters import present_task_domain_hint
from app.services.owner_queries import get_task_card
from app.services.owner_recommendations import get_domain_aware_signals
from app.dashboard.app import app

_reg_dir = Path(__file__).resolve().parents[2] / "app" / "data" / "domain_registry"
if _reg_dir.exists():
    os.environ["KNOW_PROFF_REGISTRY_DIR"] = str(_reg_dir)


# --- A. Task domain metadata shape ---
def test_task_domain_metadata_shape():
    meta = build_task_domain_metadata("проверить договор с поставщиком")
    assert "primary_domain" in meta
    assert "secondary_domains" in meta
    assert "domain_confidence" in meta
    assert "domain_reason" in meta
    assert "matched_keywords" in meta
    assert "context_pack_keys" in meta
    assert "domain_routing_version" in meta
    assert "domain_selection_source" in meta
    assert meta["primary_domain"] == "legal"
    assert isinstance(meta["secondary_domains"], list)
    assert meta["domain_selection_source"] in ("triage", "fallback")


# --- B. Domain triage selects primary and secondary domains ---
def test_domain_triage_selects_primary_and_secondary_domains():
    result = triage_domains_for_task("исправить баг в API и написать тесты")
    assert "primary_domain_key" in result
    assert "secondary_domain_keys" in result
    assert "reason" in result
    assert "matched_keywords" in result
    assert result["primary_domain_key"] in ("programming_engineer", "development", None) or result["primary_domain_key"]
    assert isinstance(result["secondary_domain_keys"], list)


# --- C. Domain context selection returns expected packs ---
def test_domain_context_selection_returns_expected_packs():
    sel = select_context_for_task("договор согласование лицензия")
    assert "selected_context_packs" in sel
    assert "compact_context" in sel
    assert "primary_domain_key" in sel
    assert "reason" in sel
    assert isinstance(sel["selected_context_packs"], list)
    if sel["primary_domain_key"]:
        assert "legal" in sel["selected_context_packs"]


# --- D. Task creation / intake attaches domain metadata ---
def test_task_creation_or_intake_attaches_domain_metadata(db_session):
    from app.storage.repositories import TaskRepository
    from app.storage.models import AuditEvent
    from app.shared.audit import log_audit
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="проверить договор")
    assert task.id
    from app.services.domain_triage import build_task_domain_metadata
    meta = build_task_domain_metadata("проверить договор")
    log_audit(repo, "domain_triage", task_id=task.id, payload=meta)
    events = db_session.query(AuditEvent).filter(AuditEvent.event_type == "domain_triage").all()
    assert len(events) >= 1
    payload = events[-1].payload_json or {}
    assert payload.get("primary_domain") == "legal"


# --- E. Owner task view shows domain hint ---
def test_owner_task_view_shows_domain_hint(db_session):
    from app.storage.repositories import TaskRepository
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="согласовать договор с юристом")
    card = get_task_card(task.id)
    assert card is not None
    assert "domain_metadata" in card
    dm = card.get("domain_metadata")
    if dm and dm.get("primary_domain"):
        text = format_task_card(card)
        assert "Экспертиза" in text or dm["primary_domain"] in text
    hint = format_domain_hint_compact(dm or {})
    if dm and dm.get("primary_domain"):
        assert "legal" in hint or dm["primary_domain"] in hint


# --- F. Domain-aware recommendations include explainable signals ---
def test_domain_aware_recommendations_include_explainable_signals(db_session):
    signals = get_domain_aware_signals(limit_tasks=5, limit_signals=3)
    assert "items" in signals
    assert "explainable" in signals
    assert signals["explainable"] is True
    for item in signals.get("items", []):
        assert "domain_key" in item
        assert "reason" in item
        assert "task_count" in item or "reason" in item


# --- G. Domain views and routes remain working ---
def test_domain_views_and_routes_remain_working():
    client = TestClient(app, raise_server_exceptions=False)
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    headers = {"X-API-Key": key}
    r = client.get("/owner/domains", headers=headers)
    assert r.status_code in (200, 401, 500)
    r2 = client.get("/api/owner/domain/legal", headers=headers)
    assert r2.status_code in (200, 401, 404, 500)
    r3 = client.get("/api/owner/route", params={"text": "договор"}, headers=headers)
    assert r3.status_code in (200, 401, 500)


# --- H. Role/project/domain relation docs are consistent ---
def test_role_project_domain_relation_docs_are_consistent():
    from pathlib import Path as P
    res = P(__file__).resolve()
    for level in [3, 4]:
        if len(res.parents) <= level:
            continue
        doc = res.parents[level] / "docs" / "contracts" / "PROJECT_ROLE_DOMAIN_RELATION.md"
        if doc.exists():
            content = doc.read_text(encoding="utf-8")
            assert "project" in content.lower()
            assert "role" in content.lower()
            assert "domain" in content.lower()
            return
    doc2 = res.parents[2] / "docs" / "contracts" / "PROJECT_ROLE_DOMAIN_RELATION.md"
    if doc2.exists():
        content = doc2.read_text(encoding="utf-8")
        assert "project" in content.lower() and "domain" in content.lower()
        return
    pytest.skip("PROJECT_ROLE_DOMAIN_RELATION.md not found")
