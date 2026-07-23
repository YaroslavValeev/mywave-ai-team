# app/shared/dashboard_session.py — cookie-сессия владельца для HTML Dashboard
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

from app.shared.auth import get_owner_api_key, normalize_owner_key_input
from app.shared.dashboard_link import _signing_key_material

COOKIE_NAME = "mw_owner_session"


def session_ttl_seconds() -> int:
    """Срок cookie: по умолчанию 30 дней (solo owner)."""
    try:
        days = float(os.getenv("DASHBOARD_SESSION_DAYS", "30"))
    except ValueError:
        days = 30.0
    return max(3600, int(days * 86400))


def sign_owner_session() -> str | None:
    key = _signing_key_material()
    if not key:
        return None
    exp = int(time.time()) + session_ttl_seconds()
    body = f"1:owner:{exp}"
    sig = hmac.new(key, body.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{body}|{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def verify_owner_session(token: str | None) -> bool:
    if not token or not str(token).strip():
        return False
    key = _signing_key_material()
    if not key:
        return False
    try:
        pad = "=" * (-len(token.strip()) % 4)
        raw = base64.urlsafe_b64decode((token.strip() + pad).encode("ascii")).decode("utf-8")
        if "|" not in raw:
            return False
        body, sig = raw.rsplit("|", 1)
        parts = body.split(":")
        if len(parts) != 3 or parts[0] != "1" or parts[1] != "owner":
            return False
        if int(parts[2]) < int(time.time()):
            return False
        expected = hmac.new(key, body.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    except (ValueError, UnicodeDecodeError, OSError):
        return False


def request_has_owner_session(request) -> bool:
    try:
        raw = request.cookies.get(COOKIE_NAME)
    except Exception:
        return False
    return verify_owner_session(normalize_owner_key_input(raw))


def owner_password_ok(password: str | None) -> bool:
    """Пароль входа = OWNER_API_KEY (или короткий DASHBOARD_PIN, если задан)."""
    provided = normalize_owner_key_input(password)
    if not provided:
        return False
    pin = normalize_owner_key_input(os.getenv("DASHBOARD_PIN"))
    if pin and provided == pin:
        return True
    expected = get_owner_api_key()
    return bool(expected and provided == expected)
