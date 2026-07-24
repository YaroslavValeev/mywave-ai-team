"""Strict CrewAI no-fallback policy (ORCHESTRATION_ALLOW_FALLBACK=false)."""

from __future__ import annotations

import pytest


def test_crewai_strict_required_auto_and_crewai(monkeypatch):
    from app.orchestrator import crewai_bridge as bridge

    assert bridge.crewai_strict_required({"engine": "auto", "allow_fallback": False}) is True
    assert bridge.crewai_strict_required({"engine": "crewai", "allow_fallback": False}) is True
    assert bridge.crewai_strict_required({"engine": "auto", "allow_fallback": True}) is False
    assert bridge.crewai_strict_required({"engine": "rule_based", "allow_fallback": False}) is False


def test_is_crewai_enabled_strict_auto_without_creds(monkeypatch):
    from app.orchestrator import crewai_bridge as bridge

    monkeypatch.setattr(
        bridge,
        "get_orchestration_config",
        lambda: {"engine": "auto", "allow_fallback": False},
    )
    monkeypatch.setattr(bridge, "has_llm_credentials", lambda: False)
    assert bridge.is_crewai_enabled() is True


def test_triage_raises_when_strict_auto_and_crewai_empty(monkeypatch):
    from app.orchestrator import triage as triage_module

    monkeypatch.setattr(
        triage_module,
        "get_orchestration_config",
        lambda: {"engine": "auto", "allow_fallback": False},
    )
    monkeypatch.setattr(triage_module, "run_crewai_triage", lambda text: {})
    monkeypatch.setattr(triage_module, "detect_revenue_intent", lambda text: False)
    monkeypatch.setattr(triage_module, "detect_marketing_plan_intent", lambda text: False)
    monkeypatch.setattr(triage_module, "get_last_crewai_error", lambda: "AuthenticationError: bad key")

    with pytest.raises(RuntimeError, match="CrewAI triage required.*AuthenticationError"):
        triage_module.run_triage("# TASK feature delivery без LLM")


def test_run_crewai_triage_raises_with_detail_in_strict(monkeypatch):
    from app.orchestrator import crewai_bridge as bridge

    monkeypatch.setattr(
        bridge,
        "get_orchestration_config",
        lambda: {"engine": "crewai", "allow_fallback": False},
    )
    monkeypatch.setattr(bridge, "is_crewai_enabled", lambda: True)
    monkeypatch.setattr(bridge, "_run_json_task", lambda **kwargs: {})
    bridge._set_last_crewai_error("RateLimitError: 429")

    with pytest.raises(RuntimeError, match="RateLimitError"):
        bridge.run_crewai_triage("check broadcast feature")


def test_normalize_triage_keeps_scalars():
    from app.orchestrator.crewai_bridge import TRIAGE_KEYS, _normalize_payload

    out = _normalize_payload(
        {
            "domain": "PRODUCT_DEV",
            "task_type": ["feature_delivery"],
            "criticality": "LOW",
            "plan_or_execute": "PLAN",
            "execute_gate": "OWNER_APPROVAL_IF_PROD",
        },
        TRIAGE_KEYS,
    )
    assert out["domain"] == "PRODUCT_DEV"
    assert out["task_type"] == "feature_delivery"
    assert out["criticality"] == "LOW"
