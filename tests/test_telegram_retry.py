import asyncio


def test_send_with_retry_retries_network_errors(monkeypatch):
    """send_with_retry повторяет временные ошибки и завершает успешно."""
    from aiogram.exceptions import TelegramNetworkError
    from aiogram.methods import SendMessage
    from app.bot import notify as notify_module

    method = SendMessage(chat_id=1, text="hello")
    attempts = {"count": 0}
    sleeps = []

    class FakeBot:
        async def send_message(self, chat_id, text, **kwargs):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise TelegramNetworkError(method, "temporary network issue")
            return True

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(
        notify_module,
        "get_orchestration_config",
        lambda: {"telegram_retry_attempts": 4, "telegram_retry_base_seconds": 0.1},
    )
    monkeypatch.setattr(notify_module.asyncio, "sleep", fake_sleep)

    ok = asyncio.run(notify_module.send_with_retry(FakeBot(), 1, "hello"))

    assert ok is True
    assert attempts["count"] == 3
    assert sleeps == [0.1, 0.2]
