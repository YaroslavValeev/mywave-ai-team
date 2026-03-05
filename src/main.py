# src/main.py
# Минимальный entrypoint (заглушка). Подключи CrewAI внутри orchestrator.

import asyncio
from bot.telegram_gateway import run_bot

if __name__ == "__main__":
    asyncio.run(run_bot())
