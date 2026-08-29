"""Stage-boundary Telegram notify (unit)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch


def test_notify_stage_sync_respects_flag(monkeypatch):
    monkeypatch.setenv("TELEGRAM_STAGE_NOTIFY", "false")
    from app.config import get_orchestration_config

    assert get_orchestration_config()["telegram_stage_notify"] is False

    with patch("app.bot.notify.notify_stage", new_callable=AsyncMock) as mock_stage:
        from app.bot.notify import notify_stage_sync

        notify_stage_sync(1, "triage", detail="x")
        mock_stage.assert_not_called()


def test_proactive_notifications_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PROACTIVE_NOTIFY_ENABLED", raising=False)
    from app.config import get_orchestration_config

    assert get_orchestration_config()["telegram_proactive_notify"] is False


def test_send_owner_message_does_not_create_bot_without_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PROACTIVE_NOTIFY_ENABLED", "false")
    with patch("app.bot.notify.Bot") as bot_class:
        from app.bot.notify import send_owner_message

        ok = asyncio.run(send_owner_message("background message"))

    assert ok is False
    bot_class.assert_not_called()


def test_notify_stage_message_format():
    with patch("app.bot.notify.send_owner_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        from app.bot.notify import notify_stage

        ok = asyncio.run(notify_stage(42, "pipeline", detail="handoffs=3"))
        assert ok is True
        text = mock_send.call_args[0][0]
        assert "42" in text
        assert "Конвейер" in text


def test_notify_stage_truncates_long_detail():
    with patch("app.bot.notify.send_owner_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        from app.bot.notify import notify_stage

        long_detail = "x" * 500
        asyncio.run(notify_stage(7, "triage", detail=long_detail))
        text = mock_send.call_args[0][0]
        assert len(text) < 280
        assert "…" in text


def test_notify_stage_sync_never_raises(monkeypatch):
    monkeypatch.setenv("TELEGRAM_STAGE_NOTIFY", "true")
    with patch("app.bot.notify.notify_stage", side_effect=RuntimeError("boom")):
        from app.bot.notify import notify_stage_sync

        notify_stage_sync(1, "court", detail="y")  # must not raise
