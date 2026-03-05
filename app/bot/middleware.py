# app/bot/middleware.py — RedactionMiddleware (HF-2: логи)
from typing import Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from app.shared.redaction import redact
import logging

logger = logging.getLogger(__name__)


class RedactionMiddleware(BaseMiddleware):
    """Маскирует PII/токены в логах перед выводом."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable],
        event: TelegramObject,
        data: dict,
    ):
        if isinstance(event, Message) and event.text:
            data["_original_text"] = event.text
            logger.debug("Message: %s", redact(event.text))
        elif isinstance(event, CallbackQuery) and event.data:
            logger.debug("Callback: %s", redact(event.data))
        return await handler(event, data)
