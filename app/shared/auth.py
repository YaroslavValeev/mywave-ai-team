# app/shared/auth.py — OWNER_API_KEY (HF-1)
import logging
import os

from fastapi import Header, HTTPException, Query

logger = logging.getLogger(__name__)


def normalize_owner_key_input(value: str | None) -> str:
    """Пробелы/CRLF и UTF-8 BOM в начале (часто из .env, сохранённого в «Блокноте»)."""
    if value is None:
        return ""
    return str(value).strip().lstrip("\ufeff")


def get_owner_api_key() -> str:
    """Канонический ключ: OWNER_API_KEY, fallback DASHBOARD_API_KEY (нормализованный ввод)."""
    for env_name in ("OWNER_API_KEY", "DASHBOARD_API_KEY"):
        raw = os.getenv(env_name)
        if not raw:
            continue
        key = normalize_owner_key_input(raw)
        if key:
            if env_name == "DASHBOARD_API_KEY":
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


def dashboard_web_key_ok(request, x_api_key: str | None) -> bool:
    """Браузерный доступ: заголовок X-API-Key или query ?api_key= (как index/office)."""
    expected = get_owner_api_key()
    if not expected:
        return False
    hdr = normalize_owner_key_input(x_api_key or request.headers.get("x-api-key"))
    q = normalize_owner_key_input(request.query_params.get("api_key"))
    provided = hdr or q
    return bool(provided and provided == expected)


def assert_dashboard_task_write(request, task_id: int) -> None:
    """POST на /tasks/{id}/…: ключ владельца или валидный ?link= для этого task_id."""
    from app.shared.dashboard_link import verify_task_link

    if dashboard_web_key_ok(request, request.headers.get("x-api-key")):
        return
    link = normalize_owner_key_input(request.query_params.get("link"))
    if link and verify_task_link(task_id, link):
        return
    raise HTTPException(
        status_code=401,
        detail="Unauthorized: valid X-API-Key or signed ?link= required for this action",
    )


async def require_owner_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    api_key: str = Query(None, description="Локальный dev: ?api_key=OWNER_API_KEY"),
) -> None:
    """FastAPI Depends: X-API-Key или ?api_key= (для браузера на localhost)."""
    expected = get_owner_api_key()
    if not expected:
        raise HTTPException(status_code=500, detail="Server misconfiguration: OWNER_API_KEY not set")
    key = normalize_owner_key_input(x_api_key or api_key)
    if not key or key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized: valid X-API-Key required")
