"""Map governance domain → L2 agent_cluster (ADR-007)."""

from __future__ import annotations

DOMAIN_TO_CLUSTER: dict[str, str] = {
    "MEDIA_OPS": "MEDIA",
    "AUTHORITY_CONTENT": "MEDIA",
    "PRODUCT_DEV": "STRATEGY",
    "GAME": "STRATEGY",
    "BUSINESS": "STRATEGY",
    "INFRA": "STRATEGY",
    "SPONSOR_PLATFORM": "STRATEGY",
    "EVENTS": "EVENTS",
    "RND_EXTREME": "EVENTS",
    "RUZA": "KNOWLEDGE",
    "CLIENTOPS": "KNOWLEDGE",
}


def agent_cluster_for_domain(domain: str | None) -> str:
    if not domain:
        return "UNKNOWN"
    return DOMAIN_TO_CLUSTER.get(str(domain).strip().upper(), "UNKNOWN")


def attach_agent_cluster(triage_result: dict) -> dict:
    """Idempotent: set agent_cluster from domain."""
    out = dict(triage_result or {})
    out["agent_cluster"] = agent_cluster_for_domain(out.get("domain"))
    return out
