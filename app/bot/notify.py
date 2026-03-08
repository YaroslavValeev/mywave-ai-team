# app/bot/notify.py — отправка уведомлений Owner в Telegram
import asyncio
import logging
import os
from typing import Any, Optional

from aiogram import Bot

from app.config import get_telegram_config
from app.shared.redaction import redact

logger = logging.getLogger(__name__)


async def send_owner_message(text: str, parse_mode: str = "Markdown", reply_markup: Optional[Any] = None) -> bool:
    """Отправить сообщение Owner. Возвращает True при успехе."""
    cfg = get_telegram_config()
    token = cfg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = cfg.get("owner_chat_id") or os.getenv("OWNER_CHAT_ID")
    if not token or not chat_id:
        logger.warning("Cannot send: TELEGRAM_BOT_TOKEN or OWNER_CHAT_ID not set")
        return False
    try:
        bot = Bot(token=token)
        kwargs = {"parse_mode": parse_mode}
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        await bot.send_message(int(chat_id), redact(text), **kwargs)
        return True
    except Exception as e:
        logger.exception("send_owner_message failed: %s", e)
        return False


async def notify_pr_ready(task_id: int, pr_url: str, summary: str, dashboard_url: str):
    """Уведомление о готовом PR + кнопки."""
    from app.bot.handlers import build_owner_buttons_with_merged
    msg = f"""📋 Task #{task_id} — PR готов

{redact(summary)[:400]}...

🔗 PR: {pr_url}
📊 [Dashboard]({dashboard_url}/tasks/{task_id})"""
    markup = build_owner_buttons_with_merged(task_id).as_markup()
    await send_owner_message(msg, reply_markup=markup)
