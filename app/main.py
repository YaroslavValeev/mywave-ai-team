# app/main.py — entrypoint: bot + dashboard
import asyncio
import logging
import multiprocessing
import os
import sys

# Добавить корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.repositories import init_db, get_session_factory
from app.bot.run import run_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_dashboard_process():
    from app.dashboard.app import run_dashboard
    run_dashboard()


async def main():
    # HF-1: fail-fast если Dashboard без OWNER_API_KEY
    from app.shared.auth import require_owner_key_at_startup
    require_owner_key_at_startup()
    # Инициализация БД (retry при старте в Docker)
    for i in range(10):
        try:
            init_db()
            logger.info("DB initialized")
            break
        except Exception as e:
            logger.warning("DB init retry %s/10: %s", i + 1, e)
            await asyncio.sleep(2)
    else:
        raise RuntimeError("DB init failed after 10 retries")

    # Запуск Dashboard в отдельном процессе
    dashboard_proc = multiprocessing.Process(target=run_dashboard_process, daemon=True)
    dashboard_proc.start()
    logger.info("Dashboard started on port 8080")

    # Запуск бота
    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())
