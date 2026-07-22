# src/main.py
# DEPRECATED: legacy entrypoint. Use `python -m app.main` instead.
# Kept for backward compatibility with docker/Dockerfile (legacy path).

import asyncio
from bot.telegram_gateway import run_bot

if __name__ == "__main__":
    asyncio.run(run_bot())
