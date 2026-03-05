# app/config — загрузка конфигурации
import os
from pathlib import Path
import yaml

CONFIG_DIR = Path(__file__).parent


def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_routing() -> dict:
    return _load_yaml("routing")


def get_policy() -> dict:
    return _load_yaml("policy")


def get_telegram_config() -> dict:
    cfg = _load_yaml("telegram")
    # Env override
    if token := os.getenv("TELEGRAM_BOT_TOKEN"):
        cfg["bot_token"] = token
    if owner := os.getenv("OWNER_CHAT_ID"):
        cfg["owner_chat_id"] = owner
    return cfg


def get_owner_config() -> dict:
    return _load_yaml("owner_config")


def get_dashboard_config() -> dict:
    cfg = _load_yaml("dashboard")
    if url := os.getenv("DASHBOARD_URL"):
        cfg["base_url"] = url
    return cfg
