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

    with pytest.raises(RuntimeError, match="CrewAI triage required"):
        triage_module.run_triage("# TASK feature delivery без LLM")
