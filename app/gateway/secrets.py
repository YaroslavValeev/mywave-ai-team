# app/gateway/secrets.py — централизованное хранение секретов
# Агенты/runner'ы НЕ получают сырые ключи, только capabilities через gateway.

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_capability(scope: str, action: str) -> Optional[str]:
    """
    Возвращает capability/токен для scope+action (минимальный доступ).
    scope: "github", "telegram", "db", "api"
    action: "read", "write", "pr", etc.
    """
    # TODO: реализовать IAM-центр, эпизодические токены, ротацию
    # Пока — fallback на env, но логируем доступ
    key = f"GATEWAY_{scope.upper()}_{action.upper()}"
    val = os.environ.get(key)
    if val:
        logger.info("Gateway capability requested: %s", scope)
    return val


def has_owner_key() -> bool:
    """Проверка наличия OWNER_API_KEY (обязателен для gateway)."""
    return bool(os.environ.get("OWNER_API_KEY"))
