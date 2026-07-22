# app/gateway/router.py — единая точка запроса capability + опциональный audit.
from __future__ import annotations

from typing import Any, Optional

from app.gateway.registry import CapabilityResolution, get_gateway_registry


def evaluate_capability(
    scope: str,
    action: str,
    *,
    task_id: Optional[int] = None,
    audit_repo: Any = None,
) -> CapabilityResolution:
    """
    Запросить capability. Секрет при успехе — только в поле value (не логировать, не отдавать в API наружу).
    Если передан audit_repo (TaskRepository), пишется audit-событие gateway_capability_request.
    """
    reg = get_gateway_registry()
    r = reg.resolve(scope.strip(), action.strip())

    if audit_repo is not None and task_id is not None:
        try:
            from app.shared.audit import log_audit

            log_audit(
                audit_repo,
                "gateway_capability_request",
                task_id=task_id,
                payload={
                    "scope": scope,
                    "action": action,
                    "ok": r.ok,
                    "runtime": r.runtime,
                    "message": r.message if not r.ok else "granted",
                },
            )
        except Exception:
            pass

    return r


def get_secret_for_legacy_scope(scope: str, action: str) -> Optional[str]:
    """Совместимость со старым API get_capability(scope, action)."""
    r = get_gateway_registry().resolve(scope, action)
    return r.value if r.ok else None
