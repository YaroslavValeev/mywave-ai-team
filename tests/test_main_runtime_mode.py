import asyncio

import pytest

from app import main as app_main


def test_telegram_polling_enabled_defaults_to_true(monkeypatch):
    monkeypatch.delenv("TELEGRAM_POLLING_ENABLED", raising=False)

    assert app_main.telegram_polling_enabled() is True


@pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE"])
def test_telegram_polling_can_be_disabled(monkeypatch, value):
    monkeypatch.setenv("TELEGRAM_POLLING_ENABLED", value)

    assert app_main.telegram_polling_enabled() is False


def test_dashboard_only_mode_does_not_start_bot(monkeypatch):
    class DashboardProcess:
        exitcode = 0

        def __init__(self, **_kwargs):
            self._alive_checks = 0

        def start(self):
            return None

        def is_alive(self):
            self._alive_checks += 1
            return self._alive_checks == 1

    async def fail_if_bot_starts():
        raise AssertionError("Telegram bot must not start in Dashboard-only mode")

    async def no_wait(_seconds):
        return None

    monkeypatch.setenv("TELEGRAM_POLLING_ENABLED", "false")
    monkeypatch.setattr(app_main, "init_db", lambda: None)
    monkeypatch.setattr(app_main.multiprocessing, "Process", DashboardProcess)
    monkeypatch.setattr(app_main, "run_bot", fail_if_bot_starts)
    monkeypatch.setattr(app_main.asyncio, "sleep", no_wait)
    monkeypatch.setattr("app.shared.auth.require_owner_key_at_startup", lambda: None)

    with pytest.raises(RuntimeError, match="Dashboard process stopped with exit code 0"):
        asyncio.run(app_main.main())
