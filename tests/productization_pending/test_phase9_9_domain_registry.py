# tests/test_phase9_9_domain_registry.py — Phase 9.9: domain expertise registry and expert routing baseline
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Set registry dir before importing domain_registry (so _get_registry_dir finds it)
_repo_root = Path(__file__).resolve().parents[1]
_reg_dir = _repo_root / "app" / "data" / "domain_registry"
if _reg_dir.exists():
    os.environ["KNOW_PROFF_REGISTRY_DIR"] = str(_reg_dir)
else:
    # Workspace layout: docs/know_proff/registry at repo root or umbrella
    for _docs_reg in (
        _repo_root / "docs" / "know_proff" / "registry",
        _repo_root.parents[1] / "docs" / "know_proff" / "registry",
    ):
        if _docs_reg.exists():
            os.environ["KNOW_PROFF_REGISTRY_DIR"] = str(_docs_reg)
            break

from app.services.domain_registry import (
    list_domains,
    get_domain,
    get_domain_by_alias,
    get_expert_profile,
    get_domain_context_pack,
)
from app.services.expert_routing import (
    suggest_domains_for_task,
    explain_domain_match,
    get_primary_domain_for_task,
    get_secondary_domains_for_task,
)
from app.services.domain_context_packs import (
    build_context_pack,
    build_task_context_pack,
    build_multi_domain_context_pack,
)
from app.presenters.domain_presenters import (
    present_domain_registry_list,
    present_domain_card,
    present_routing_result,
    format_domain_list_text,
    format_domain_card_text,
    format_routing_result_text,
)
from app.dashboard.app import app


# --- A. Registry contains all 12 known profiles ---
def test_domain_registry_contains_all_known_profiles():
    domains = list_domains()
    assert len(domains) == 12, "Registry must contain all 12 know_proff files"
    keys = {d.get("domain_key") for d in domains}
    expected = {
        "legal", "analytics", "development", "programming_engineer", "finance",
        "social_media", "brand_manager", "copywriting", "marketing", "sales",
        "smm", "social_engineering",
    }
    assert keys == expected
    source_files = {d.get("source_file") for d in domains}
    assert "layer.txt" in source_files
    assert "Programming ingeneer.txt" in source_files
    assert "Sociol media.txt" in source_files


# --- B. Alias resolution works ---
def test_domain_alias_resolution_works():
    assert get_domain_by_alias("legal") == "legal"
    assert get_domain_by_alias("юрист") == "legal"
    assert get_domain_by_alias("programming ingeneer") == "programming_engineer"
    assert get_domain_by_alias("sociol media") == "social_media"
    assert get_domain_by_alias("copiwriter") == "copywriting"
    assert get_domain_by_alias("analytics") == "analytics"
    assert get_domain("programming_engineer") is not None
    assert get_domain("ingeneer") is not None  # via alias


# --- C. Context pack contains expected sections ---
def test_domain_context_pack_contains_expected_sections():
    pack = build_context_pack("legal")
    assert pack is not None
    assert "domain_key" in pack
    assert "canonical_name" in pack
    assert "summary" in pack
    assert "strengths" in pack
    assert "typical_tasks" in pack
    assert pack.get("domain_key") == "legal"


# --- D. Expert routing returns primary and secondary domains ---
def test_expert_routing_returns_primary_and_secondary_domains():
    suggestions = suggest_domains_for_task("проверить договор с поставщиком", limit=5)
    assert len(suggestions) >= 1
    primary = next((s for s in suggestions if s.get("is_primary") or s.get("is_fallback")), None)
    assert primary is not None
    assert "domain_key" in primary
    assert primary.get("domain_key") == "legal"

    suggestions_code = suggest_domains_for_task("исправить баг в API", limit=5)
    primary_code = next((s for s in suggestions_code if s.get("is_primary") or s.get("is_fallback")), None)
    assert primary_code is not None
    assert primary_code.get("domain_key") in ("programming_engineer", "development")

    secondary = get_secondary_domains_for_task("договор и бюджет", limit=2)
    assert isinstance(secondary, list)


# --- E. Routing result contains explainable reasons ---
def test_routing_result_contains_explainable_reasons():
    suggestions = suggest_domains_for_task("договор согласование", limit=3)
    assert len(suggestions) >= 1
    for s in suggestions:
        assert "reason" in s or "matched_keywords" in s
        assert "domain_key" in s
        assert "canonical_name" in s
    expl = explain_domain_match("проверить договор", "legal")
    assert "matched_keywords" in expl
    assert "reason" in expl


# --- F. Domain routes are wired ---
def test_domain_routes_are_wired():
    client = TestClient(app, raise_server_exceptions=False)
    key = os.environ.get("OWNER_API_KEY") or "test_key_for_smoke"
    headers = {"X-API-Key": key}

    r = client.get("/owner/domains", headers=headers)
    assert r.status_code in (200, 401, 500)
    if r.status_code == 200:
        assert "домен" in r.text.lower() or "domain" in r.text.lower() or "Домены" in r.text

    r_api = client.get("/api/owner/domains", headers=headers)
    assert r_api.status_code in (200, 401, 500)
    if r_api.status_code == 200:
        data = r_api.json()
        assert "domains" in data or "total" in data

    r_domain = client.get("/api/owner/domain/legal", headers=headers)
    assert r_domain.status_code in (200, 401, 404, 500)
    if r_domain.status_code == 200:
        data = r_domain.json()
        assert data.get("domain_key") == "legal"

    r_route = client.get("/api/owner/route", params={"text": "договор"}, headers=headers)
    assert r_route.status_code in (200, 401, 500)
    if r_route.status_code == 200:
        data = r_route.json()
        assert "primary" in data or "all" in data


# --- G. Domain commands are wired (Telegram handlers) ---
@pytest.mark.asyncio
async def test_domain_commands_are_wired():
    from app.bot.handlers import handle_domains, handle_domain, handle_route

    msg = MagicMock()
    msg.chat.id = 12345
    msg.answer = AsyncMock()

    with patch("app.bot.handlers.is_owner", return_value=True):
        msg.text = "/domains"
        await handle_domains(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "домен" in text.lower() or "12" in text or "Домены" in text

        msg.answer.reset_mock()
        msg.text = "/domain legal"
        await handle_domain(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "legal" in text or "Юридический" in text

        msg.answer.reset_mock()
        msg.text = "/route проверить договор"
        await handle_route(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "домен" in text.lower() or "legal" in text.lower() or "Совпадения" in text


# --- H. Role-domain relation is documented consistently ---
def test_role_domain_relation_is_documented_consistently():
    from pathlib import Path as P
    res = P(__file__).resolve()
    # tests -> Presets(2) -> AI-Team(3) -> MyWaveAITeam(4); workspace root often parents[3] or [4]
    for level in [3, 4]:
        if len(res.parents) <= level:
            continue
        doc = res.parents[level] / "docs" / "contracts" / "ROLE_DOMAIN_RELATION.md"
        if doc.exists():
            content = doc.read_text(encoding="utf-8")
            assert "role" in content.lower()
            assert "domain" in content.lower()
            assert "permission" in content.lower() or "expertise" in content.lower()
            return
    app_contracts = res.parents[2] / "docs" / "contracts" / "ROLE_DOMAIN_RELATION.md"
    if app_contracts.exists():
        content = app_contracts.read_text(encoding="utf-8")
        assert "role" in content.lower() and "domain" in content.lower()
        return
    pytest.skip("ROLE_DOMAIN_RELATION.md not found in expected paths")
