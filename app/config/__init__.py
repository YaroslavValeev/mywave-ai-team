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


def get_gateway_config() -> dict:
    """Реестр OpenClaw-style capabilities (app/config/gateway.yaml)."""
    return _load_yaml("gateway")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_orchestration_config() -> dict:
    return {
        # По умолчанию auto: сначала CrewAI + роли STEP_PROFILES; при недоступности LLM — fallback (см. ORCHESTRATION_ALLOW_FALLBACK).
        "engine": os.getenv("ORCHESTRATION_ENGINE", "auto").strip().lower() or "auto",
        "allow_fallback": os.getenv("ORCHESTRATION_ALLOW_FALLBACK", "true").strip().lower() not in {"0", "false", "no"},
        "telegram_retry_attempts": int(os.getenv("TELEGRAM_RETRY_ATTEMPTS", "4")),
        "telegram_retry_base_seconds": float(os.getenv("TELEGRAM_RETRY_BASE_SECONDS", "1.5")),
        # Stage-boundary progress in Telegram (не полный stream реплик).
        "telegram_stage_notify": os.getenv("TELEGRAM_STAGE_NOTIFY", "true").strip().lower()
        not in {"0", "false", "no"},
        "retention_days": int(os.getenv("RETENTION_DAYS", str(get_policy().get("logging", {}).get("retention_days", 90)))),
        "crewai_model": os.getenv("CREWAI_MODEL", "").strip(),
        "crewai_provider": os.getenv("CREWAI_PROVIDER", "").strip(),
        "crewai_temperature": float(os.getenv("CREWAI_TEMPERATURE", "0.2")),
        "crewai_timeout": int(os.getenv("CREWAI_TIMEOUT", "120")),
        "crewai_max_tokens": _int_env("CREWAI_MAX_TOKENS", 8192),
        "crewai_use_responses_api": os.getenv("CREWAI_USE_RESPONSES_API", "false").strip().lower() in {"1", "true", "yes"},
        "owner_brief_limit": _int_env("ORCHESTRATION_OWNER_BRIEF_LIMIT", 12000),
        "attachment_max_per_file": _int_env("ORCHESTRATION_ATTACHMENT_MAX_CHARS_PER_FILE", 60000),
        "attachment_max_total": _int_env("ORCHESTRATION_ATTACHMENT_MAX_TOTAL", 240000),
        "rule_fallback_excerpt_per_file": _int_env("ORCHESTRATION_RULE_EXCERPT_PER_FILE", 8000),
        # ADR-006: local (RU Ollama) vs cloud (EU LiteLLM → OpenAI)
        "llm_tier_default": (
            os.getenv("LLM_TIER_DEFAULT", "").strip().lower()
            or (
                "local"
                if (os.getenv("LLM_LOCAL_BASE_URL") or "").strip()
                else (
                    "cloud"
                    if (os.getenv("LLM_CLOUD_BASE_URL") or os.getenv("OPENAI_API_KEY") or "").strip()
                    else "local"
                )
            )
        ),
        "llm_local_base_url": os.getenv("LLM_LOCAL_BASE_URL", "").strip(),
        "llm_local_api_key": os.getenv("LLM_LOCAL_API_KEY", "").strip(),
        "llm_local_model": os.getenv("LLM_LOCAL_MODEL", "").strip(),
        "llm_local_provider": os.getenv("LLM_LOCAL_PROVIDER", "openai").strip(),
        "llm_cloud_base_url": os.getenv("LLM_CLOUD_BASE_URL", "").strip(),
        "llm_cloud_api_key": os.getenv("LLM_CLOUD_API_KEY", "").strip(),
        "llm_cloud_model": os.getenv("LLM_CLOUD_MODEL", "").strip(),
        "llm_cloud_provider": os.getenv("LLM_CLOUD_PROVIDER", "openai").strip(),
    }
