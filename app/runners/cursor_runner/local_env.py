# app/runners/cursor_runner/local_env.py — единое слияние env для локального runner с gateway (без дублирования секретов).
from __future__ import annotations

import os
from typing import Optional

from app.gateway.secrets import github_token, openai_api_key


def merge_gateway_secrets_into_env(base: Optional[dict] = None) -> dict:
    """
    Дополняет окружение токенами из gateway, только если соответствующие переменные ещё не заданы.
    Так локальные вызовы согласованы с app/config/gateway.yaml и не противоречат выдаче capability.
    """
    out = dict(os.environ)
    if base:
        out.update(base)

    gh = github_token()
    if gh and not (out.get("GH_TOKEN") or out.get("GITHUB_TOKEN")):
        out["GH_TOKEN"] = gh

    oa = openai_api_key()
    if oa and not out.get("OPENAI_API_KEY"):
        out["OPENAI_API_KEY"] = oa

    return out
