# app/orchestrator/llm_tier.py — local vs cloud (EU) LLM selection
from __future__ import annotations

import logging
import os
import re
from contextvars import ContextVar
from typing import Any

from app.config import get_orchestration_config

logger = logging.getLogger(__name__)

_active_tier: ContextVar[str] = ContextVar("llm_tier", default="")

CLOUD_TAGS = ("#CLOUD", "#OPENAI", "#LLM_CLOUD")
LOCAL_TAGS = ("#LOCAL", "#OLLAMA", "#LLM_LOCAL")


def get_active_llm_tier() -> str:
    token = (_active_tier.get() or "").strip().lower()
    if token in {"local", "cloud"}:
        return token
    return resolve_llm_tier()


def set_active_llm_tier(tier: str | None) -> None:
    value = (tier or "").strip().lower()
    if value not in {"local", "cloud", ""}:
        value = ""
    _active_tier.set(value)


def resolve_llm_tier(
    *,
    owner_text: str = "",
    business_action: dict | None = None,
    criticality: str | None = None,
) -> str:
    """Resolve tier: explicit task override → tags → env default → legacy."""
    ba = business_action if isinstance(business_action, dict) else {}
    explicit = str(ba.get("llm_tier") or "").strip().lower()
    if explicit in {"local", "cloud"}:
        return explicit

    text = owner_text or ""
    upper = text.upper()
    if any(tag in upper for tag in CLOUD_TAGS):
        return "cloud"
    if any(tag in upper for tag in LOCAL_TAGS):
        return "local"

    cfg = get_orchestration_config()
    default = str(cfg.get("llm_tier_default") or "local").strip().lower()
    if default in {"local", "cloud"}:
        return default

    # Legacy single-endpoint mode: if only cloud-looking key without local URL → cloud
    if cfg.get("llm_local_base_url"):
        return "local"
    if cfg.get("llm_cloud_base_url") or (os.getenv("OPENAI_API_KEY") or "").strip():
        return "cloud"
    return "local"


def merge_llm_tier_into_business_action(
    business_action: dict | None,
    tier: str,
) -> dict:
    ba = dict(business_action) if isinstance(business_action, dict) else {}
    ba["llm_tier"] = tier
    return ba


def detect_tier_tag_in_text(owner_text: str) -> str | None:
    upper = (owner_text or "").upper()
    if any(tag in upper for tag in CLOUD_TAGS):
        return "cloud"
    if any(tag in upper for tag in LOCAL_TAGS):
        return "local"
    return None


def strip_tier_tags(owner_text: str) -> str:
    text = owner_text or ""
    for tag in (*CLOUD_TAGS, *LOCAL_TAGS):
        text = re.sub(re.escape(tag), "", text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text).strip()


def endpoint_for_tier(tier: str | None = None) -> dict[str, str]:
    """Return base_url, api_key, model, provider for the active or given tier."""
    cfg = get_orchestration_config()
    chosen = (tier or get_active_llm_tier() or "local").strip().lower()
    if chosen not in {"local", "cloud"}:
        chosen = "local"

    if chosen == "cloud":
        base = (
            cfg.get("llm_cloud_base_url")
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("CREWAI_BASE_URL")
            or ""
        ).strip()
        key = (
            cfg.get("llm_cloud_api_key")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("CREWAI_API_KEY")
            or ""
        ).strip()
        model = (
            cfg.get("llm_cloud_model")
            or cfg.get("crewai_model")
            or os.getenv("CREWAI_DEFAULT_MODEL")
            or "gpt-4.1-nano"
        ).strip()
        provider = (cfg.get("llm_cloud_provider") or cfg.get("crewai_provider") or "openai").strip()
    else:
        base = (
            cfg.get("llm_local_base_url")
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("CREWAI_BASE_URL")
            or ""
        ).strip()
        key = (cfg.get("llm_local_api_key") or "").strip()
        if not key:
            base_l = base.lower()
            key = "ollama" if ("11434" in base_l or "ollama" in base_l) else ("local" if base else "")
        model = (
            cfg.get("llm_local_model")
            or cfg.get("crewai_model")
            or os.getenv("CREWAI_DEFAULT_MODEL")
            or "llama3.2:3b"
        ).strip()
        provider = (cfg.get("llm_local_provider") or "openai").strip()
        # Local without URL: fall back to legacy cloud vars if present
        if not base and (os.getenv("OPENAI_API_KEY") or "").strip() and not cfg.get("llm_cloud_base_url"):
            key = (os.getenv("OPENAI_API_KEY") or "").strip()
            model = (
                cfg.get("crewai_model")
                or os.getenv("CREWAI_DEFAULT_MODEL")
                or model
            ).strip()

    return {
        "tier": chosen,
        "base_url": base,
        "api_key": key,
        "model": model,
        "provider": provider,
    }


def tier_credentials_ok(tier: str | None = None) -> bool:
    ep = endpoint_for_tier(tier)
    if (ep.get("base_url") or "").strip():
        return True
    if ep.get("tier") == "local":
        return False
    return bool((ep.get("api_key") or "").strip())


def describe_active_endpoint() -> str:
    ep = endpoint_for_tier()
    base = ep["base_url"] or "(default openai api)"
    return f"tier={ep['tier']} model={ep['model']} base={base}"
