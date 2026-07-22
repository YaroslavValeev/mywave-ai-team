# app/gateway/secrets.py — централизованная выдача секретов через GatewayRegistry (OpenClaw-style).
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_capability(scope: str, action: str) -> Optional[str]:
    """
    Вернуть секрет для пары scope+action согласно app/config/gateway.yaml.
    Агенты и runner'ы не должны читать os.environ напрямую для перечисленных возможностей.
    """
    from app.gateway.registry import get_gateway_registry

    r = get_gateway_registry().resolve(scope, action)
    if r.ok and r.value:
        logger.info("Gateway capability granted: %s.%s (%s)", scope, action, r.runtime)
        return r.value
    logger.debug("Gateway capability denied: %s.%s — %s", scope, action, r.message)
    return None


def has_owner_key() -> bool:
    """Проверка наличия OWNER_API_KEY (частые вызовы — без шума в логах)."""
    return bool(os.getenv("OWNER_API_KEY"))


def github_token() -> Optional[str]:
    """Токен GitHub для runner / интеграций (GH_TOKEN или GITHUB_TOKEN)."""
    return get_capability("github", "pr")


def openai_api_key() -> Optional[str]:
    """Ключ OpenAI API если настроен."""
    return get_capability("openai", "api")
