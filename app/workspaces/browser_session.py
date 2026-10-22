"""Short-lived scoped cookies, signed by the dedicated credential, never by owner key."""

import base64
import hashlib
import hmac
import json
import secrets
import time

COOKIE = "mywave_project_session"
PATH = "/api/workspaces"
TTL = 900


def issue(principal, key):
    now = int(time.time())
    payload = json.dumps(
        {
            "p": principal,
            "iat": now,
            "exp": now + TTL,
            "nonce": secrets.token_urlsafe(16),
        },
        separators=(",", ":"),
    ).encode()
    value = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()
    return value + "." + signature


def resolve(value, bindings):
    if not value or len(value) > 1024:
        return None
    try:
        payload, signature = value.split(".")
        data = json.loads(
            base64.b64decode(
                payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True
            )
        )
        now = int(time.time())
        if (
            type(data["iat"]) is not int
            or type(data["exp"]) is not int
            or not data["iat"] <= now < data["exp"]
            or data["exp"] - data["iat"] != TTL
        ):
            return None
        for principal, key in bindings:
            expected = hmac.new(
                key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()
            if data["p"] == principal and hmac.compare_digest(signature, expected):
                return principal
    except (ValueError, TypeError, KeyError, UnicodeError):
        pass
    return None
