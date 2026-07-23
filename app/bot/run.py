# app/bot/run.py — запуск Telegram-бота
import logging
import os

from aiogram import Bot, Dispatcher

from app.config import get_telegram_config
from app.bot.handlers import register_handlers
from app.bot.middleware import RedactionMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _build_bot(token: str) -> Bot:
    """
    Bot с опциональным HTTP(S)/SOCKS-прокси (EU-мост для РФ).
    TELEGRAM_PROXY_URL примеры:
      http://127.0.0.1:1080
      socks5://USER:PASS@72.56.99.214:1080
    """
    proxy = (os.getenv("TELEGRAM_PROXY_URL") or "").strip()
    if not proxy:
        return Bot(token=token)
    try:
        from aiogram.client.session.aiohttp import AiohttpSession

        session = AiohttpSession(proxy=proxy)
        logger.info("Telegram proxy enabled via TELEGRAM_PROXY_URL")
        return Bot(token=token, session=session)
    except Exception as exc:
        logger.warning("TELEGRAM_PROXY_URL set but session failed (%s); using direct Bot", exc)
        return Bot(token=token)


async def run_bot():
    cfg = get_telegram_config()
    token = cfg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing. Set in .env or config/telegram.yaml")

    bot = _build_bot(token)
    dp = Dispatcher()

    dp.message.middleware(RedactionMiddleware())
    dp.callback_query.middleware(RedactionMiddleware())
    register_handlers(dp)

    logger.info("Bot starting (polling)...")
    await dp.start_polling(bot)
