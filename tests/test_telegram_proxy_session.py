# tests/test_telegram_proxy_session.py — TELEGRAM_PROXY_URL wiring
import os


def test_build_bot_without_proxy(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PROXY_URL", raising=False)
    from app.bot.run import _build_bot

    bot = _build_bot("123456:TESTTOKEN_FOR_UNIT")
    assert bot is not None
    # Без прокси — стандартная session
    assert bot.session is not None


def test_build_bot_with_proxy_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "http://127.0.0.1:9")
    from app.bot.run import _build_bot

    bot = _build_bot("123456:TESTTOKEN_FOR_UNIT")
    assert bot is not None
