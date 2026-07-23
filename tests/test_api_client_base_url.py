"""Default Control API base URL must be the live prod host."""

from __future__ import annotations

import importlib


def test_api_client_default_base_url_is_mywavewake(monkeypatch):
    monkeypatch.delenv("MYWAVE_BASE_URL", raising=False)
    monkeypatch.delenv("DASHBOARD_URL", raising=False)
    import app.shared.api_client as api_client

    importlib.reload(api_client)
    assert api_client.BASE_URL == "https://agm.mywavewake.ru"
