# app/bot/run.py — запуск Telegram-бота
import logging
import os

from aiogram import Bot, Dispatcher

from app.config import get_telegram_config
from app.bot.handlers import register_handlers
from app.bot.middleware import RedactionMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_bot():
    cfg = get_telegram_config()
    token = cfg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing. Set in .env or config/telegram.yaml")

    bot = Bot(token=token)
    dp = Dispatcher()

    dp.message.middleware(RedactionMiddleware())
    dp.callback_query.middleware(RedactionMiddleware())
    register_handlers(dp)

    logger.info("Bot starting (polling)...")
    await dp.start_polling(bot)
