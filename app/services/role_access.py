# app/services/role_access.py — Phase 12.1: role/access hardening
"""Централизованная логика разрешения роли, проверки доступа к маршрутам и действиям."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

KNOWN_ROLES = frozenset({"owner", "operator", "executor", "reviewer"})
FALLBACK_ON_UNKNOWN = None  # deny by default

# Route access: role -> set of route names (normalized, e.g. /owner, /actions)
_ROUTE_ACCESS: dict[str, set[str]] = {
    "owner": {
        "/", "/owner", "/owner/portfolio", "/owner/project", "/owner/interventions",
        "/owner/decision-support", "/owner/domains", "/owner/domain",
        "/views/operator", "/views/executor", "/views/reviewer",
        "/actions", "/actions/run", "/api/actions", "/api",
    },
    "operator": {
        "/", "/owner/project", "/owner/interventions", "/owner/decision-support",
        "/views/operator", "/actions", "/actions/run", "/api/actions",
    },
    "executor": {
        "/", "/owner/project", "/owner/decision-support", "/views/executor",
        "/actions", "/actions/run", "/api/actions",
    },
    "reviewer": {
        "/", "/owner/project", "/owner/interventions", "/owner/decision-support",
        "/views/reviewer", "/actions", "/actions/run", "/api/actions",
    },
}


def _log_role_access_event(event_type: str, payload: dict[str, Any]) -> None:
    """Записать событие доступа в audit."""
    try:
        from app.storage.repositories import get_session_factory, TaskRepository
        from app.shared.audit import log_audit

        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_audit(repo, event_type, task_id=None, payload=payload)
    except Exception as e:
        logger.warning("Failed to log role access event %s: %s", event_type, e)


def resolve_actor_role(channel: str, context: dict[str, Any]) -> Optional[str]:
    """
    Определить роль актора по каналу и контексту.
    channel: "web" | "telegram" | "api"
    context: api_key_valid?, chat_id?, is_owner? (для telegram)
    Returns: роль или None (deny).
    """
    channel = (channel or "").lower().strip()
    if channel in ("web", "api"):
        if context.get("api_key_valid"):
            return "owner"
        return None
    if channel == "telegram":
        if context.get("is_owner"):
            return "owner"
        chat_id = context.get("chat_id")
        if chat_id is not None:
            cid = str(chat_id)
            for env_key, role in [
                ("OPERATOR_CHAT_IDS", "operator"),
                ("EXECUTOR_CHAT_IDS", "executor"),
                ("REVIEWER_CHAT_IDS", "reviewer"),
            ]:
                val = os.getenv(env_key)
                if val:
                    ids = [x.strip() for x in val.split(",") if x.strip()]
                    if cid in ids:
                        return role
        return None
    return None


def deny_or_fallback_role(resolved: Optional[str]) -> Optional[str]:
    """
    Если роль не в KNOWN_ROLES — вернуть FALLBACK_ON_UNKNOWN (deny).
    Иначе вернуть роль как есть.
    """
    if not resolved or not isinstance(resolved, str):
        return FALLBACK_ON_UNKNOWN
    r = resolved.strip().lower()
    if r in KNOWN_ROLES:
        return r
    return FALLBACK_ON_UNKNOWN


def can_access_route(role_key: str, route_name: str) -> bool:
    """
    Проверить, может ли роль получить доступ к маршруту.
    route_name: нормализованный путь, например /owner или /owner/project.
    """
    role = deny_or_fallback_role(role_key)
    if not role:
        return False
    allowed = _ROUTE_ACCESS.get(role)
    if not allowed:
        return False
    # exact or prefix match
    rn = (route_name or "").strip()
    if not rn.startswith("/"):
        rn = "/" + rn
    for a in allowed:
        if rn == a or (a != "/" and rn.startswith(a + "/")):
            return True
    return role == "owner"  # owner has all


def can_execute_safe_action(role_key: str, action_name: str, context: Optional[dict[str, Any]] = None) -> bool:
    """Проверить, может ли роль выполнить safe action. Делегирует в action_center."""
    from app.services.action_center import can_execute_action

    role = deny_or_fallback_role(role_key)
    if not role:
        return False
    return can_execute_action(role, action_name or "", context)


def get_role_access_summary(role_key: str) -> dict[str, Any]:
    """
    Краткое описание доступа для роли: routes_count, actions_count, role_label.
    """
    role = deny_or_fallback_role(role_key)
    if not role:
        return {"role": None, "routes_count": 0, "actions_count": 0, "label": "denied"}

    from app.services.action_center import list_available_actions

    actions = list_available_actions(role)
    routes = _ROUTE_ACCESS.get(role, set())
    labels = {"owner": "Owner", "operator": "Operator", "executor": "Executor", "reviewer": "Reviewer"}
    return {
        "role": role,
        "routes_count": len(routes),
        "actions_count": len(actions),
        "label": labels.get(role, role),
    }


def resolve_and_log(
    channel: str,
    context: dict[str, Any],
    actor: str = "",
) -> Optional[str]:
    """
    Разрешить роль и залогировать role_resolved (и unknown_role_fallback при fallback).
    Returns: роль или None.
    """
    resolved = resolve_actor_role(channel, context)
    effective = deny_or_fallback_role(resolved)
    fallback_used = resolved is not None and effective != resolved
    if fallback_used:
        _log_role_access_event("unknown_role_fallback", {
            "channel": channel,
            "actor": actor,
            "resolved": resolved,
            "fallback_role": effective,
        })
    _log_role_access_event("role_resolved", {
        "channel": channel,
        "actor": actor,
        "role": effective,
        "fallback_used": fallback_used,
    })
    return effective


def check_route_access_and_log(
    role_key: str,
    route_name: str,
    actor: str = "",
) -> bool:
    """Проверить доступ к маршруту и залогировать grant/deny."""
    allowed = can_access_route(role_key, route_name)
    event = "route_access_granted" if allowed else "route_access_denied"
    _log_role_access_event(event, {
        "route": route_name,
        "role": role_key,
        "actor": actor,
        "granted": allowed,
        "reason": None if allowed else "role not allowed for route",
    })
    return allowed


def log_critical_route_access_if_enabled(route_name: str, actor: str = "web", role: str = "owner") -> None:
    """Phase 12.2: опционально логировать route_access_granted для критичных entrypoints. Env: ROUTE_ACCESS_AUDIT_ENABLED=1."""
    if os.getenv("ROUTE_ACCESS_AUDIT_ENABLED", "").lower() in ("1", "true", "yes"):
        _log_role_access_event("route_access_granted", {
            "route": route_name,
            "role": role,
            "actor": actor,
            "granted": True,
        })


def check_action_access_and_log(
    role_key: str,
    action_name: str,
    actor: str = "",
    context: Optional[dict[str, Any]] = None,
) -> bool:
    """Проверить доступ к действию и залогировать grant/deny."""
    allowed = can_execute_safe_action(role_key, action_name, context)
    event = "action_access_granted" if allowed else "action_access_denied"
    _log_role_access_event(event, {
        "action_name": action_name,
        "role": role_key,
        "actor": actor,
        "granted": allowed,
        "reason": None if allowed else "role not allowed for action",
    })
    return allowed
