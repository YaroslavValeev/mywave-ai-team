# Gateway (OpenClaw-style) — реестр capabilities и API.
import pytest


@pytest.fixture(autouse=True)
def _clear_gateway_cache():
    from app.gateway.registry import reload_gateway_registry_for_tests

    reload_gateway_registry_for_tests()
    yield
    reload_gateway_registry_for_tests()


def test_registry_resolves_github_when_token_set(monkeypatch):
    from app.gateway.registry import reload_gateway_registry_for_tests

    reload_gateway_registry_for_tests()
    monkeypatch.setenv("GH_TOKEN", "ghp_test_secret")
    from app.gateway.registry import get_gateway_registry

    r = get_gateway_registry().resolve("github", "pr")
    assert r.ok is True
    assert r.value == "ghp_test_secret"
    assert r.runtime == "server"


def test_registry_denies_local_filesystem_on_server():
    from app.gateway.registry import get_gateway_registry

    r = get_gateway_registry().resolve("filesystem_local", "scan")
    assert r.ok is False
    assert r.runtime == "local_runner"
    assert "сервер" in r.message.lower() or "локальн" in r.message.lower() or "runner" in r.message.lower()


def test_gateway_catalog_api(client, auth_headers):
    r = client.get("/api/gateway/catalog", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["model"] == "gateway-v1"
    assert isinstance(data["capabilities"], list)
    assert any(c.get("scope") == "github" for c in data["capabilities"])


def test_gateway_evaluate_without_secret(client, auth_headers, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    r = client.post(
        "/api/gateway/evaluate",
        headers=auth_headers,
        json={"scope": "github", "action": "pr"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["secret_configured"] is False


def test_system_health_includes_gateway(client, auth_headers):
    r = client.get("/api/system/health", headers=auth_headers)
    assert r.status_code == 200
    checks = r.json().get("checks", {})
    assert "gateway" in checks
