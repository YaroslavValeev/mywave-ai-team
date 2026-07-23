"""Unit tests for AgentsControlClient (mocked HTTP)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agents_http_client import AgentsControlClient, AgentsControlError


def _mock_response(payload: dict, status: int = 200):
    raw = json.dumps(payload).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_health_ok():
    client = AgentsControlClient("http://example.test", "key")
    with patch("urllib.request.urlopen", return_value=_mock_response({"status": "ok"})):
        assert client.health()["status"] == "ok"


def test_create_task_owner_text():
    client = AgentsControlClient("http://example.test", "key")
    with patch("urllib.request.urlopen", return_value=_mock_response({"id": 3})) as m:
        out = client.create_task(owner_text="#TASK hi")
        assert out["id"] == 3
        req = m.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.full_url.endswith("/api/tasks")


def test_from_env_requires_key(monkeypatch):
    monkeypatch.delenv("AGENTS_API_KEY", raising=False)
    monkeypatch.delenv("OWNER_API_KEY", raising=False)
    monkeypatch.setenv("AGENTS_CONTROL_API_URL", "http://127.0.0.1:8088")
    with pytest.raises(AgentsControlError):
        AgentsControlClient.from_env()


def test_http_error():
    client = AgentsControlClient("http://example.test", "key")
    import urllib.error

    err = urllib.error.HTTPError("http://x", 401, "Unauthorized", hdrs=None, fp=MagicMock())
    err.fp.read.return_value = b'{"detail":"no"}'
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(AgentsControlError) as ei:
            client.list_tasks()
        assert ei.value.status == 401


def test_create_task_default_criticality_medium():
    client = AgentsControlClient("http://example.test", "key")
    with patch("urllib.request.urlopen", return_value=_mock_response({"id": 9})) as m:
        client.create_task(domain="PRODUCT_DEV", task_type="general", payload={})
        body = json.loads(m.call_args[0][0].data.decode("utf-8"))
        assert body["criticality"] == "MEDIUM"


def test_approve_rework_clarify_mark_merged_paths():
    client = AgentsControlClient("http://example.test", "key")
    cases = [
        ("approve", "/api/tasks/5/approve", {"note": "ok"}),
        ("rework", "/api/tasks/5/rework", {"note": "fix"}),
        ("clarify", "/api/tasks/5/clarify", {"note": "?"}),
        ("mark_merged", "/api/tasks/5/merged", None),
    ]
    for method_name, expected_path, note_kw in cases:
        with patch("urllib.request.urlopen", return_value=_mock_response({"ok": True})) as m:
            method = getattr(client, method_name)
            if note_kw is None:
                method(5)
            else:
                method(5, note=note_kw["note"])
            req = m.call_args[0][0]
            assert req.get_method() == "POST"
            assert req.full_url.endswith(expected_path)


def test_create_task_auto_run_flag():
    client = AgentsControlClient("http://example.test", "key")
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_response({"id": 7, "status": "WAIT_OWNER"}),
    ) as m:
        out = client.create_task(owner_text="#TASK auto", auto_run=True)
        assert out["id"] == 7
        body = json.loads(m.call_args[0][0].data.decode("utf-8"))
        assert body["auto_run"] is True
