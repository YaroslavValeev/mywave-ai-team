# app/services/action_center.py — Phase 9.8: safe role-aware action orchestration
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from app.storage.repositories import get_session_factory, TaskRepository
from app.services.action_audit import log_action

# Registry: action_name -> {category, allowed_roles, handler}
# handler(context) -> (success: bool, result_summary: str, error_message: str | None)
ActionHandler = Callable[[dict[str, Any]], tuple[bool, str, Optional[str]]]

_ACTION_REGISTRY: dict[str, dict[str, Any]] = {}


def _register(
    name: str,
    category: str,
    allowed_roles: list[str],
    handler: ActionHandler,
    safe: bool = True,
    approval_required: bool = False,
) -> None:
    _ACTION_REGISTRY[name] = {
        "category": category,
        "allowed_roles": allowed_roles,
        "handler": handler,
        "safe": safe,
        "approval_required": approval_required,
    }


def _molt_health_check() -> tuple[bool, str]:
    from app.services.owner_queries import _molt_health_check as check
    return check()


def _run_async(coro) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


# --- Handlers (reuse existing layers) ---
def _refresh_status(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    from app.services.owner_queries import get_system_status_summary
    data = get_system_status_summary()
    s = "state=%s, active=%s, pending_approvals=%s" % (
        data.get("state", "?"),
        data.get("active_tasks_count", 0),
        data.get("pending_approvals_count", 0),
    )
    return True, "Status refreshed: " + s, None


def _send_summary_now(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    from app.owner_summary import build_detailed_summary
    from app.bot.notify import send_owner_notification
    payload = build_detailed_summary()
    try:
        ok = _run_async(send_owner_notification("daily_summary", payload))
        return (ok, "Summary sent to Telegram.", None) if ok else (False, "Send failed.", "Notification not sent")
    except Exception as e:
        return False, "Send failed.", str(e)


def _send_digest_now(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    from app.services.owner_recommendations import get_strategic_weekly_digest
    from app.bot.notify import send_owner_notification
    payload = get_strategic_weekly_digest()
    try:
        ok = _run_async(send_owner_notification("strategic_weekly_digest", payload))
        return (ok, "Digest sent to Telegram.", None) if ok else (False, "Send failed.", "Notification not sent")
    except Exception as e:
        return False, "Send failed.", str(e)


def _recheck_molt_health(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    ok, msg = _molt_health_check()
    return True, "Molt: %s (%s)" % (msg, "up" if ok else "down"), None


def _run_smoke_check(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    from app.services.owner_queries import get_system_status_summary
    ok, msg = _molt_health_check()
    data = get_system_status_summary()
    if ok:
        return True, "Smoke OK. Molt=%s, state=%s, active=%s" % (msg, data.get("state", "?"), data.get("active_tasks_count", 0)), None
    return False, "Smoke failed: Molt %s" % msg, msg


def _acknowledge_degraded(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    return True, "Degraded state acknowledged (logged).", None


def _retry_runtime_check(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    return _recheck_molt_health(context)


def _rebuild_focus_list(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    from app.services.owner_portfolio import get_portfolio_focus_list
    data = get_portfolio_focus_list(limit=20)
    n = data.get("count", len(data.get("items", [])))
    return True, "Focus list rebuilt: %s items." % n, None


def _notify_owner_now(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    return _send_summary_now(context)


def _open_decision_queue(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    from app.services.owner_recommendations import get_decision_queue
    data = get_decision_queue(limit=50)
    n = data.get("count", len(data.get("items", [])))
    return True, "Decision queue refreshed: %s items." % n, None


def _refresh_project_view(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    from app.services.project_queries import list_projects
    data = list_projects(limit=100)
    n = len(data) if isinstance(data, list) else data.get("count", 0)
    return True, "Project view refreshed: %s projects." % n, None


def _trigger_project_summary(context: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    return _send_summary_now(context)


# --- Register all baseline actions ---
def _build_registry() -> None:
    if _ACTION_REGISTRY:
        return
    _register("refresh_status", "informational", ["owner", "operator", "executor", "reviewer"], _refresh_status)
    _register("refresh_project_view", "informational", ["owner", "executor"], _refresh_project_view)
    _register("send_summary_now", "control", ["owner"], _send_summary_now)
    _register("send_digest_now", "control", ["owner"], _send_digest_now)
    _register("recheck_molt_health", "recovery", ["owner", "operator"], _recheck_molt_health)
    _register("run_smoke_check", "recovery", ["owner", "operator"], _run_smoke_check)
    _register("acknowledge_degraded", "recovery", ["owner", "operator"], _acknowledge_degraded)
    _register("retry_runtime_check", "recovery", ["owner", "operator"], _retry_runtime_check)
    _register("rebuild_focus_list", "workflow", ["owner"], _rebuild_focus_list)
    _register("notify_owner_now", "control", ["owner"], _notify_owner_now)
    _register("open_decision_queue", "informational", ["owner", "reviewer"], _open_decision_queue)
    _register("trigger_project_summary", "control", ["owner"], _trigger_project_summary)


def list_available_actions(role: str, context: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Список действий, доступных для роли."""
    _build_registry()
    out = []
    for name, meta in _ACTION_REGISTRY.items():
        if role in meta["allowed_roles"]:
            out.append({
                "action_name": name,
                "category": meta["category"],
                "safe": meta["safe"],
                "approval_required": meta["approval_required"],
            })
    return out


def can_execute_action(role: str, action_name: str, context: Optional[dict[str, Any]] = None) -> bool:
    """Может ли роль выполнить действие."""
    _build_registry()
    meta = _ACTION_REGISTRY.get(action_name)
    if not meta:
        return False
    return role in meta["allowed_roles"]


def execute_action(
    action_name: str,
    role: str,
    context: Optional[dict[str, Any]] = None,
    actor: Optional[str] = None,
) -> dict[str, Any]:
    """
    Выполнить действие. Проверяет роль, вызывает handler, пишет audit, возвращает result.
    Returns: {success, result_summary, error_message, action_id, status}
    """
    _build_registry()
    context = context or {}
    actor = actor or "unknown"
    started_at = datetime.now(timezone.utc).isoformat()
    action_id = str(uuid.uuid4())

    if not can_execute_action(role, action_name, context):
        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            log_action(
                repo, action_id, action_name, role, actor, "failure", started_at,
                datetime.now(timezone.utc).isoformat(),
                "Role not allowed.",
                context=context,
                error_message="Role %s is not allowed to run action %s" % (role, action_name),
            )
        return {
            "success": False,
            "result_summary": "Role not allowed to run this action.",
            "error_message": "Role %s is not allowed to run action %s" % (role, action_name),
            "action_id": action_id,
            "status": "failure",
        }

    meta = _ACTION_REGISTRY[action_name]
    handler = meta["handler"]
    success = False
    result_summary = ""
    error_message = None
    try:
        success, result_summary, error_message = handler(context)
    except Exception as e:
        result_summary = "Action failed."
        error_message = str(e)

    finished_at = datetime.now(timezone.utc).isoformat()
    status = "success" if success else "failure"
    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        log_action(
            repo, action_id, action_name, role, actor, status, started_at, finished_at,
            result_summary, context=context, error_message=error_message,
        )

    return {
        "success": success,
        "result_summary": result_summary,
        "error_message": error_message,
        "action_id": action_id,
        "status": status,
    }


def get_action_result(action_name: str, role: str, context: Optional[dict[str, Any]] = None, actor: Optional[str] = None) -> dict[str, Any]:
    """Alias: execute and return result (for API symmetry)."""
    return execute_action(action_name, role, context=context, actor=actor)


def execute_action_for_collaboration_execution(
    action_name: str,
    *,
    role: str,
    execution_id: str,
    actor: Optional[str] = None,
) -> dict[str, Any]:
    """
    Phase 11.4: выполнить зарегистрированный safe action с контекстом collaboration execution.
    Не меняет границы безопасности: те же проверки ролей, что и execute_action.
    """
    ctx: dict[str, Any] = {"collaboration_execution_id": execution_id}
    return execute_action(action_name, role, context=ctx, actor=actor)
