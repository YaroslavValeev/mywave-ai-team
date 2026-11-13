# app/presenters/role_access_presenters.py — Phase 12.1: human-readable role/access messages

from __future__ import annotations

from typing import Any, Optional


def present_access_denied(
    reason: str = "role not allowed",
    route: Optional[str] = None,
    action: Optional[str] = None,
    role: Optional[str] = None,
) -> dict[str, Any]:
    """Формирует структуру отказа в доступе для API/Telegram."""
    parts = []
    if route:
        parts.append(f"route={route}")
    if action:
        parts.append(f"action={action}")
    if role:
        parts.append(f"role={role}")
    detail = reason
    if parts:
        detail = f"{reason} ({', '.join(parts)})"
    return {
        "access_denied": True,
        "reason": reason,
        "detail": detail,
        "route": route,
        "action": action,
        "role": role,
    }


def format_access_denied_message(
    reason: str = "Доступ запрещён.",
    route: Optional[str] = None,
    action: Optional[str] = None,
) -> str:
    """Human-readable сообщение об отказе для пользователя (Telegram, web)."""
    if action:
        return f"Действие «{action}» недоступно для вашей роли. {reason}"
    if route:
        return f"Маршрут {route} недоступен. {reason}"
    return reason


def format_role_summary(summary: dict[str, Any]) -> str:
    """Краткое текстовое описание доступа роли."""
    role = summary.get("role")
    label = summary.get("label", role or "—")
    routes = summary.get("routes_count", 0)
    actions = summary.get("actions_count", 0)
    if not role:
        return "Доступ отсутствует."
    return f"Роль: {label}. Маршрутов: {routes}, действий: {actions}."


def format_refusal_text(
    for_action: bool = False,
    action_name: str = "",
    route_name: str = "",
) -> str:
    """Компактный текст отказа для логов и уведомлений."""
    if for_action and action_name:
        return f"Отказ: действие {action_name} не разрешено для роли."
    if route_name:
        return f"Отказ: маршрут {route_name} не разрешён для роли."
    return "Отказ: недостаточно прав."
