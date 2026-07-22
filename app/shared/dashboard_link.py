# app/shared/dashboard_link.py — подписанные ссылки на HTML Dashboard (без X-API-Key в браузере)
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

from app.shared.auth import get_owner_api_key


def _signing_key_material() -> bytes:
    """Секрет HMAC: DASHBOARD_LINK_SECRET или производная от OWNER_API_KEY."""
    explicit = (os.getenv("DASHBOARD_LINK_SECRET") or "").strip()
    if explicit:
        return explicit.encode("utf-8")
    k = get_owner_api_key()
    if not k:
        return b""
    return hmac.new(k.encode("utf-8"), b"mywave.dashboard.signed_link.v1", hashlib.sha256).digest()


def _link_ttl_seconds() -> int:
    try:
        return max(60, int(os.getenv("DASHBOARD_LINK_TTL_SECONDS", "3600")))
    except ValueError:
        return 3600


def _b64url_decode_padded(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def sign_task_link(task_id: int) -> str | None:
    """
    Токен для ?link= на страницах /tasks/{id} и связанных GET.
    Возвращает None, если OWNER_API_KEY не задан (нельзя подписать).
    """
    key = _signing_key_material()
    if not key:
        return None
    exp = int(time.time()) + _link_ttl_seconds()
    body = f"1:{int(task_id)}:{exp}"
    sig = hmac.new(key, body.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{body}|{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def verify_task_link(task_id: int, token: str) -> bool:
    """Проверка подписи и срока; task_id должен совпадать с телом токена."""
    if not token or not str(token).strip():
        return False
    key = _signing_key_material()
    if not key:
        return False
    try:
        raw = _b64url_decode_padded(token.strip()).decode("utf-8")
        if "|" not in raw:
            return False
        body, sig = raw.rsplit("|", 1)
        parts = body.split(":")
        if len(parts) != 3 or parts[0] != "1":
            return False
        tid_s, exp_s = parts[1], parts[2]
        if int(tid_s) != int(task_id):
            return False
        if int(exp_s) < int(time.time()):
            return False
        expected = hmac.new(key, body.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    except (ValueError, UnicodeDecodeError, OSError):
        return False
