# app/gateway/registry.py — реестр capabilities (OpenClaw-style), резолв секретов из env.
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from app.config import get_gateway_config


@dataclass(frozen=True)
class CapabilityResolution:
    """Результат запроса capability (значение секрета — только для внутреннего использования)."""

    ok: bool
    scope: str
    action: str
    value: Optional[str]
    message: str
    runtime: str  # server | local_runner | unknown
    server_resolvable: bool


class GatewayRegistry:
    """Загрузка gateway.yaml и выдача секретов по scope/action без дублирования логики в агентах."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self._scopes: dict[str, Any] = (raw.get("scopes") or {}) if isinstance(raw, dict) else {}

    def resolve(self, scope: str, action: str) -> CapabilityResolution:
        scope = (scope or "").strip()
        action = (action or "").strip()
        if not scope or not action:
            return CapabilityResolution(
                ok=False,
                scope=scope or "?",
                action=action or "?",
                value=None,
                message="scope и action обязательны",
                runtime="unknown",
                server_resolvable=False,
            )

        spec = self._scopes.get(scope)
        if not isinstance(spec, dict):
            return CapabilityResolution(
                ok=False,
                scope=scope,
                action=action,
                value=None,
                message=f"Неизвестный scope: {scope}",
                runtime="unknown",
                server_resolvable=False,
            )

        actions = spec.get("actions") or {}
        if action not in actions:
            known = ", ".join(sorted(actions.keys())) if actions else "—"
            return CapabilityResolution(
                ok=False,
                scope=scope,
                action=action,
                value=None,
                message=f"Неизвестное действие «{action}» для scope «{scope}». Доступно: {known}",
                runtime="unknown",
                server_resolvable=bool(spec.get("server_resolvable", True)),
            )

        entry = actions[action]
        if not isinstance(entry, dict):
            entry = {}

        server_ok = bool(spec.get("server_resolvable", True))
        if not server_ok:
            rt = str(spec.get("runtime") or "local_runner")
            note = entry.get("note") or spec.get("description") or "Только вне сервера приложения."
            return CapabilityResolution(
                ok=False,
                scope=scope,
                action=action,
                value=None,
                message=str(note),
                runtime=rt,
                server_resolvable=False,
            )

        keys = entry.get("env_any_of")
        if not isinstance(keys, list) or not keys:
            return CapabilityResolution(
                ok=False,
                scope=scope,
                action=action,
                value=None,
                message="В конфиге capability не задан env_any_of",
                runtime="server",
                server_resolvable=True,
            )

        for key in keys:
            if not isinstance(key, str):
                continue
            val = os.getenv(key)
            if val:
                return CapabilityResolution(
                    ok=True,
                    scope=scope,
                    action=action,
                    value=val,
                    message=f"Выдано через переменную окружения {key}",
                    runtime="server",
                    server_resolvable=True,
                )

        missing = ", ".join(keys)
        return CapabilityResolution(
            ok=False,
            scope=scope,
            action=action,
            value=None,
            message=f"Не задан ни один из: {missing}",
            runtime="server",
            server_resolvable=True,
        )

    def catalog(self) -> list[dict[str, Any]]:
        """Публичный каталог без секретов — для Dashboard / health."""
        out: list[dict[str, Any]] = []
        for scope_name, spec in sorted(self._scopes.items()):
            if not isinstance(spec, dict):
                continue
            actions = spec.get("actions") or {}
            for action_name in sorted(actions.keys()):
                r = self.resolve(scope_name, action_name)
                status = "ready" if r.ok else ("local_only" if r.runtime == "local_runner" else "missing")
                out.append(
                    {
                        "scope": scope_name,
                        "action": action_name,
                        "description": spec.get("description", ""),
                        "server_resolvable": r.server_resolvable,
                        "runtime": r.runtime,
                        "status": status,
                        "message": r.message if not r.ok else "configured",
                    }
                )
        return out

    def health_message(self) -> tuple[str, str]:
        """(status, message) для system health: ok | warn | error"""
        if not self._scopes:
            return "warn", "gateway.yaml пуст или не загружен"
        # хотя бы один server capability готов — ok; иначе warn
        any_ready = False
        any_server = False
        for item in self.catalog():
            if item.get("server_resolvable"):
                any_server = True
            if item.get("status") == "ready":
                any_ready = True
        if any_ready:
            return "ok", "Gateway: есть хотя бы одна выданная server capability."
        if any_server:
            return "warn", "Gateway загружен, но ни одна server capability не сконфигурирована (проверьте env)."
        return "ok", "Gateway: только локальные capabilities (local_runner)."


@lru_cache(maxsize=1)
def get_gateway_registry() -> GatewayRegistry:
    return GatewayRegistry(get_gateway_config())


def reload_gateway_registry_for_tests() -> None:
    get_gateway_registry.cache_clear()
