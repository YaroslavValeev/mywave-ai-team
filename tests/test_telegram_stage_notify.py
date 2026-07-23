"""Stage-boundary Telegram notify (unit)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def test_notify_stage_sync_respects_flag(monkeypatch):
    monkeypatch.setenv("TELEGRAM_STAGE_NOTIFY", "false")
    from app.config import get_orchestration_config

    assert get_orchestration_config()["telegram_stage_notify"] is False

    with patch("app.bot.notify.notify_stage", new_callable=AsyncMock) as mock_stage:
        from app.bot.notify import notify_stage_sync

        notify_stage_sync(1, "triage", detail="x")
        mock_stage.assert_not_called()


@pytest.mark.asyncio
async def test_notify_stage_message_format():
    with patch("app.bot.notify.send_owner_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        from app.bot.notify import notify_stage

        ok = await notify_stage(42, "pipeline", detail="handoffs=3")
        assert ok is True
        text = mock_send.call_args[0][0]
        assert "42" in text
        assert "Конвейер" in text


@pytest.mark.asyncio
async def test_notify_stage_truncates_long_detail():
    with patch("app.bot.notify.send_owner_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        from app.bot.notify import notify_stage

        long_detail = "x" * 500
        await notify_stage(7, "triage", detail=long_detail)
        text = mock_send.call_args[0][0]
        assert len(text) < 280
        assert "…" in text


def test_notify_stage_sync_never_raises(monkeypatch):
    monkeypatch.setenv("TELEGRAM_STAGE_NOTIFY", "true")
    with patch("app.bot.notify.notify_stage", side_effect=RuntimeError("boom")):
        from app.bot.notify import notify_stage_sync

        notify_stage_sync(1, "court", detail="y")  # must not raise
