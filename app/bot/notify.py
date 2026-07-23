# app/bot/notify.py — отправка уведомлений Owner в Telegram
import asyncio
import logging
import os
from typing import Any, Optional

from aiogram import Bot
from aiogram.exceptions import (
    RestartingTelegram,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)

from app.config import get_telegram_config, get_orchestration_config
from app.shared.redaction import redact

logger = logging.getLogger(__name__)


async def send_with_retry(
    bot: Bot,
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[Any] = None,
) -> bool:
    """Отправить сообщение в Telegram с retry/backoff для временных ошибок."""
    cfg = get_orchestration_config()
    attempts = max(1, int(cfg.get("telegram_retry_attempts", 4)))
    base_delay = max(0.1, float(cfg.get("telegram_retry_base_seconds", 1.5)))
    safe_text = redact(text)

    for attempt in range(1, attempts + 1):
        try:
            kwargs = {}
            if parse_mode:
                kwargs["parse_mode"] = parse_mode
            if reply_markup:
                kwargs["reply_markup"] = reply_markup
            await bot.send_message(int(chat_id), safe_text, **kwargs)
            return True
        except TelegramRetryAfter as exc:
            delay = max(float(getattr(exc, "retry_after", base_delay)), base_delay)
        except (TelegramNetworkError, TelegramServerError, RestartingTelegram) as exc:
            delay = base_delay * (2 ** (attempt - 1))
        except (TelegramBadRequest, TelegramForbiddenError, TelegramUnauthorizedError, TelegramNotFound) as exc:
            logger.warning("Telegram send aborted on non-retryable error: %s", exc)
            return False
        except Exception as exc:
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("Telegram send failed on attempt %s/%s: %s", attempt, attempts, exc)

        if attempt >= attempts:
            logger.error("Telegram send exhausted retries after %s attempts", attempts)
            return False

        logger.warning("Telegram send retry %s/%s in %.1fs", attempt, attempts, delay)
        await asyncio.sleep(delay)

    return False


async def send_owner_message(text: str, parse_mode: Optional[str] = "Markdown", reply_markup: Optional[Any] = None) -> bool:
    """Отправить сообщение Owner. Возвращает True при успехе."""
    cfg = get_telegram_config()
    token = cfg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = cfg.get("owner_chat_id") or os.getenv("OWNER_CHAT_ID")
    if not token or not chat_id:
        logger.warning("Cannot send: TELEGRAM_BOT_TOKEN or OWNER_CHAT_ID not set")
        return False
    try:
        bot = Bot(token=token)
        return await send_with_retry(bot, int(chat_id), text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as exc:
        logger.exception("send_owner_message failed: %s", exc)
        return False


async def notify_pr_ready(task_id: int, pr_url: str, summary: str, dashboard_url: str):
    """Уведомление о готовом PR + кнопки."""
    from app.bot.handlers import _dashboard_tasks_url, build_owner_buttons_with_merged

    msg = f"""📋 Миссия #{task_id} — PR готов

{redact(summary)[:400]}...

🔗 PR: {pr_url}
📊 [Панель]({_dashboard_tasks_url(task_id)})"""
    markup = build_owner_buttons_with_merged(task_id).as_markup()
    await send_owner_message(msg, reply_markup=markup)


_STAGE_LABELS = {
    "triage": "🔎 Триаж готов",
    "pipeline": "⚙️ Конвейер готов",
    "roundtable": "🗣 Совещание готово",
    "court": "⚖️ Суд завершён",
}


async def notify_stage(task_id: int, stage: str, detail: str = "") -> bool:
    """Короткое уведомление о границе этапа (не stream реплик агентов)."""
    label = _STAGE_LABELS.get(stage, f"📌 Этап: {stage}")
    extra = f"\n{detail}" if detail else ""
    text = f"{label} — миссия #{task_id}{extra}"
    return await send_owner_message(text, parse_mode=None)


def notify_stage_sync(task_id: int, stage: str, detail: str = "") -> None:
    """Sync wrapper for orchestrator (best-effort; never raises to caller)."""
    cfg = get_orchestration_config()
    if not cfg.get("telegram_stage_notify", True):
        return
    try:
        coro = notify_stage(task_id, stage, detail)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
        else:
            loop.create_task(coro)
    except Exception as exc:
        logger.warning("notify_stage_sync failed task_id=%s stage=%s: %s", task_id, stage, exc)
