# app/gateway — OpenClaw-style control plane: секреты и опасные действия только через gateway.
#
# Использование:
#   from app.gateway import evaluate_capability, get_capability, gateway_catalog
#   r = evaluate_capability("github", "pr", task_id=1, audit_repo=repo)
#   if r.ok:  # значение только r.value, не логировать
#       ...

from app.gateway.registry import GatewayRegistry, CapabilityResolution, get_gateway_registry, reload_gateway_registry_for_tests
from app.gateway.router import evaluate_capability, get_secret_for_legacy_scope
from app.gateway.secrets import get_capability, github_token, openai_api_key, has_owner_key


def gateway_catalog() -> list[dict]:
    """Каталог capabilities без секретов (для API и UI)."""
    return get_gateway_registry().catalog()


def gateway_health() -> tuple[str, str]:
    """Статус для system health."""
    return get_gateway_registry().health_message()


__all__ = [
    "CapabilityResolution",
    "GatewayRegistry",
    "evaluate_capability",
    "get_capability",
    "get_secret_for_legacy_scope",
    "github_token",
    "openai_api_key",
    "has_owner_key",
    "gateway_catalog",
    "gateway_health",
    "get_gateway_registry",
    "reload_gateway_registry_for_tests",
]
