# app/shared/redaction.py — единый redaction для всех каналов (HF-2)
import re
from typing import Any

# Паттерны для маскирования
PHONE_PATTERN = re.compile(
    r"(\+?7|8)\s*[\(\s\-]?\s*\d{3}\s*[\)\s\-]?\s*\d{3}\s*[\s\-]?\d{2}\s*[\s\-]?\d{2}"
)
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)
TOKEN_PATTERN = re.compile(
    r"(?:token|key|secret|password)\s*[=:]\s*['\"]?[\w\-]{20,}['\"]?",
    re.IGNORECASE
)
API_KEY_PATTERN = re.compile(
    r"\b(?:sk|pk|xoxb|xoxp|ghp|gho)_[a-zA-Z0-9]{20,}\b"
)
MASK = "***"


def redact(text: str) -> str:
    """Маскирует телефоны, email, токены (PII + secrets)."""
    if not text or not isinstance(text, str):
        return text or ""
    out = text
    out = PHONE_PATTERN.sub(MASK, out)
    out = EMAIL_PATTERN.sub(MASK, out)
    out = TOKEN_PATTERN.sub("token=***", out)
    out = API_KEY_PATTERN.sub(MASK, out)
    return out


def scrub_secrets(text: str) -> str:
    """Строже: только токены/ключи. PII не трогает. Никогда не показываем секреты."""
    if not text or not isinstance(text, str):
        return text or ""
    out = TOKEN_PATTERN.sub("token=***", text)
    out = API_KEY_PATTERN.sub(MASK, out)
    return out


def redact_dict(d: dict) -> dict:
    """Рекурсивно маскирует значения в словаре."""
    if not isinstance(d, dict):
        return d
    out = {}
    sensitive_keys = {"token", "password", "secret", "key", "api_key", "chat_id", "phone", "email"}
    for k, v in d.items():
        key_lower = str(k).lower()
        if any(s in key_lower for s in sensitive_keys) and isinstance(v, str):
            out[k] = MASK
        elif isinstance(v, dict):
            out[k] = redact_dict(v)
        elif isinstance(v, str):
            out[k] = redact(v)
        else:
            out[k] = v
    return out
