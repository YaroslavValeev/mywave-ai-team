# tests/test_system_health_molt.py — Molt probe in collect_system_health
from unittest.mock import patch

import pytest


def test_system_health_includes_molt(client, auth_headers):
    r = client.get("/api/system/health", headers=auth_headers)
    assert r.status_code == 200
    checks = r.json().get("checks", {})
    assert "molt" in checks


def test_check_molt_not_configured(monkeypatch):
    monkeypatch.delenv("MOLT_HTTP_BASE_URL", raising=False)
    monkeypatch.setenv("MOLT_TRANSPORT_MODE", "local")

    from app.shared.system_health import _check_molt

    result = _check_molt()
    assert result["status"] == "ok"
    assert "не сконфигурирован" in result["message"].lower()


def test_check_molt_health_and_ready_ok(monkeypatch):
    monkeypatch.setenv("MOLT_TRANSPORT_MODE", "http")
    monkeypatch.setenv("MOLT_HTTP_BASE_URL", "http://molt:8765")

    def fake_probe(url: str, timeout_sec: float = 2.0):
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/ready"):
            return {"status": "ready"}
        return None

    from app.shared import system_health

    with patch.object(system_health, "_molt_probe_json", side_effect=fake_probe):
        result = system_health._check_molt()

    assert result["status"] == "ok"
    assert "готов" in result["message"].lower()


def test_check_molt_health_fail_warns(monkeypatch):
    monkeypatch.setenv("MOLT_TRANSPORT_MODE", "http")
    monkeypatch.delenv("MOLT_HTTP_BASE_URL", raising=False)

    from app.shared import system_health

    with patch.object(
        system_health,
        "_molt_probe_json",
        side_effect=OSError("connection refused"),
    ):
        result = system_health._check_molt()

    assert result["status"] == "warn"
    assert "/health" in result["message"]


def test_check_molt_ready_not_ready_warns(monkeypatch):
    monkeypatch.setenv("MOLT_HTTP_BASE_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("MOLT_TRANSPORT_MODE", "http")

    def fake_probe(url: str, timeout_sec: float = 2.0):
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/ready"):
            return {"status": "not_ready", "reason": "canonical sqlite missing"}
        return None

    from app.shared import system_health

    with patch.object(system_health, "_molt_probe_json", side_effect=fake_probe):
        result = system_health._check_molt()

    assert result["status"] == "warn"
    assert "not_ready" in result["message"]
    assert "canonical sqlite missing" in result["message"]
