# Config-level CrewAI enablement: auto + keys → on; auto without keys → off; safe fallback.


def test_has_llm_credentials_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("CREWAI_BASE_URL", raising=False)
    monkeypatch.delenv("CREWAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.orchestrator.crewai_bridge import has_llm_credentials

    assert has_llm_credentials() is True


def test_has_llm_credentials_base_url_only(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CREWAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11434")
    from app.orchestrator.crewai_bridge import has_llm_credentials

    assert has_llm_credentials() is True


def test_has_llm_credentials_none(monkeypatch):
    for key in ("OPENAI_API_KEY", "CREWAI_API_KEY", "OPENAI_BASE_URL", "CREWAI_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    from app.orchestrator.crewai_bridge import has_llm_credentials

    assert has_llm_credentials() is False


def test_is_crewai_enabled_auto_with_key(monkeypatch):
    monkeypatch.setenv("ORCHESTRATION_ENGINE", "auto")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    from app.orchestrator.crewai_bridge import is_crewai_enabled

    assert is_crewai_enabled() is True


def test_is_crewai_enabled_auto_without_keys(monkeypatch):
    monkeypatch.setenv("ORCHESTRATION_ENGINE", "auto")
    for key in ("OPENAI_API_KEY", "CREWAI_API_KEY", "OPENAI_BASE_URL", "CREWAI_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    from app.orchestrator.crewai_bridge import is_crewai_enabled

    assert is_crewai_enabled() is False


def test_is_crewai_enabled_rule_based(monkeypatch):
    monkeypatch.setenv("ORCHESTRATION_ENGINE", "rule_based")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.orchestrator.crewai_bridge import is_crewai_enabled

    assert is_crewai_enabled() is False


def test_is_crewai_enabled_strict_crewai_without_keys(monkeypatch):
    monkeypatch.setenv("ORCHESTRATION_ENGINE", "crewai")
    for key in ("OPENAI_API_KEY", "CREWAI_API_KEY", "OPENAI_BASE_URL", "CREWAI_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    from app.orchestrator.crewai_bridge import is_crewai_enabled

    assert is_crewai_enabled() is True


def test_normalize_base_url_appends_v1(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CREWAI_API_KEY", raising=False)
    monkeypatch.setenv("CREWAI_MODEL", "llama3.2")
    monkeypatch.setenv("CREWAI_PROVIDER", "")

    captured = {}

    class FakeLLM:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    from app.orchestrator import crewai_bridge as bridge

    llm = bridge._build_llm({"LLM": FakeLLM})
    assert llm is not None
    assert captured["base_url"] == "http://127.0.0.1:11434/v1"
    assert captured["api_key"] == "local"
    assert captured["model"].endswith("llama3.2") or "llama3.2" in captured["model"]
