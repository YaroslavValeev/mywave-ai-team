"""LLM tier resolution: local (Ollama) vs cloud (EU LiteLLM)."""

from __future__ import annotations


def test_resolve_cloud_tag(monkeypatch):
    monkeypatch.setenv("LLM_TIER_DEFAULT", "local")
    from app.orchestrator import llm_tier as m

    assert m.resolve_llm_tier(owner_text="#TASK #CLOUD сделай сложный план") == "cloud"
    assert m.resolve_llm_tier(owner_text="#TASK обычная задача") == "local"


def test_resolve_explicit_business_action(monkeypatch):
    monkeypatch.setenv("LLM_TIER_DEFAULT", "local")
    from app.orchestrator import llm_tier as m

    assert m.resolve_llm_tier(business_action={"llm_tier": "cloud"}) == "cloud"
    assert m.resolve_llm_tier(owner_text="#LOCAL x", business_action={"llm_tier": "cloud"}) == "cloud"


def test_endpoint_for_cloud(monkeypatch):
    monkeypatch.setenv("LLM_TIER_DEFAULT", "local")
    monkeypatch.setenv("LLM_LOCAL_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("LLM_LOCAL_MODEL", "llama3.2:3b")
    monkeypatch.setenv("LLM_CLOUD_BASE_URL", "http://72.56.99.214:4000/v1")
    monkeypatch.setenv("LLM_CLOUD_API_KEY", "sk-test-master")
    monkeypatch.setenv("LLM_CLOUD_MODEL", "gpt-4.1-nano")
    from app.orchestrator import llm_tier as m

    m.set_active_llm_tier("cloud")
    ep = m.endpoint_for_tier()
    assert ep["tier"] == "cloud"
    assert "72.56.99.214" in ep["base_url"]
    assert ep["api_key"] == "sk-test-master"
    assert ep["model"] == "gpt-4.1-nano"
    m.set_active_llm_tier("local")
    ep_l = m.endpoint_for_tier()
    assert ep_l["tier"] == "local"
    assert "ollama" in ep_l["base_url"]
