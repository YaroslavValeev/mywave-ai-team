# app/shared/auth.py — OWNER_API_KEY (HF-1)
import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

_OWNER_KEY: str | None = None


def get_owner_api_key() -> str:
    """Канонический ключ: OWNER_API_KEY, fallback DASHBOARD_API_KEY."""
    global _OWNER_KEY
    if _OWNER_KEY is not None:
        return _OWNER_KEY
    key = os.getenv("OWNER_API_KEY")
    if key:
        return key
    key = os.getenv("DASHBOARD_API_KEY")
    if key:
        logger.warning("DASHBOARD_API_KEY deprecated, use OWNER_API_KEY")
        return key
    return ""


def require_owner_key_at_startup() -> None:
    """Fail-fast: приложение не должно стартовать без ключа Dashboard."""
    key = get_owner_api_key()
    if not key:
        raise RuntimeError(
            "OWNER_API_KEY (or DASHBOARD_API_KEY) must be set for Dashboard. "
            "Set in .env to enable production mode."
        )


async def require_owner_key(x_api_key: str = Header(None, alias="X-API-Key")) -> None:
    """FastAPI Depends: проверка X-API-Key, без ключа → 401."""
    expected = get_owner_api_key()
    if not expected:
        raise HTTPException(status_code=500, detail="Server misconfiguration: OWNER_API_KEY not set")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized: valid X-API-Key required")
