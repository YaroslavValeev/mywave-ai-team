# app/mcp_server/executor.py — вызов api_client для MCP tools
# Audit: mcp_tool_invoke → POST /api/audit, request_id для корреляции.

import json
import logging
import time
import uuid
from typing import Any

from app.shared import api_client

logger = logging.getLogger(__name__)


def _write_audit(tool_name: str, task_id: int | None, success: bool, latency_ms: int, request_id: str):
    """Записать mcp_tool_invoke в audit_events на сервере."""
    payload = {"tool_name": tool_name, "actor": "mcp", "status": "ok" if success else "fail", "latency_ms": latency_ms}
    api_client.audit_event("mcp_tool_invoke", payload, task_id=task_id, request_id=request_id)


def _json_pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _resolve_task_id(arguments: dict) -> int | None:
    """task_id и mission_id в продукте совпадают; MCP принимает любой из ключей."""
    for key in ("task_id", "mission_id"):
        tid = arguments.get(key)
        if tid is None:
            continue
        try:
            return int(tid) if isinstance(tid, str) else int(tid)
        except (ValueError, TypeError):
            return None
    return None


def execute_tool(name: str, arguments: dict) -> tuple[str, bool]:
    """Выполнить tool, вернуть (text_result, success)."""
    start = time.perf_counter()
    request_id = str(uuid.uuid4())
    api_client._current_request_id = request_id
    task_id = _resolve_task_id(arguments or {})

    result_text = ""
    success = False

    try:
        if name == "tasks_list":
            data, err = api_client.tasks_list()
            if err:
                result_text = f"Error: {err}"
            else:
                result_text = _json_pretty(data or [])
                success = True

        elif name == "task_create":
            domain = arguments.get("domain", "PRODUCT_DEV")
            task_type = arguments.get("task_type", "general")
            payload = arguments.get("payload", {})
            criticality = arguments.get("criticality")
            data, err = api_client.task_create(domain, task_type, payload, criticality)
            if err:
                result_text = f"Error: {err}"
            else:
                result_text = str(data)
                success = True
                if isinstance(data, dict) and "id" in data:
                    task_id = data["id"]

        elif name == "task_update":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.task_update(
                    task_id,
                    status=arguments.get("status"),
                    pr_url=arguments.get("pr_url"),
                    commit_sha=arguments.get("commit_sha"),
                    ci_url=arguments.get("ci_url"),
                )
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = str(data)
                    success = True

        elif name == "task_mark_merged":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.task_mark_merged(task_id)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = str(data)
                    success = True

        elif name == "task_approve":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.task_approve(task_id)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = str(data)
                    success = True

        elif name == "task_rework":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.task_rework(task_id)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = str(data)
                    success = True

        elif name == "task_clarify":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.task_clarify(task_id)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = str(data)
                    success = True

        elif name == "runs_list":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.task_runs_list(task_id)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = _json_pretty(data)
                    success = True

        elif name == "execution_events_list":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                limit = int(arguments.get("limit") or 100)
                data, err = api_client.task_execution_events_list(task_id, limit=limit)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = _json_pretty(data)
                    success = True

        elif name == "task_get":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.task_get(task_id, raw=bool(arguments.get("raw")))
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = _json_pretty(data)
                    success = True

        elif name == "mission_thread":
            mid = task_id
            if mid is None:
                result_text = "Error: mission_id or task_id required"
            else:
                lim = int(arguments.get("limit") or 200)
                data, err = api_client.mission_thread_get(mid, limit=lim)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = _json_pretty(data)
                    success = True

        elif name == "artifacts_list":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.artifacts_list(task_id)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = _json_pretty(data or [])
                    success = True

        elif name == "artifacts_get":
            aid = arguments.get("artifact_id") or arguments.get("path")
            if task_id is None or aid is None:
                result_text = "Error: task_id (or mission_id) and artifact_id required"
            else:
                try:
                    aid_int = int(aid)
                except (ValueError, TypeError):
                    result_text = "Error: artifact_id must be int"
                else:
                    data, err = api_client.artifacts_get(task_id, aid_int)
                    if err:
                        result_text = f"Error: {err}"
                    else:
                        result_text = data or ""
                        success = True

        elif name == "pipeline_run":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.pipeline_run(task_id)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = str(data)
                    success = True

        elif name == "pr_create":
            tid = _resolve_task_id(arguments)
            pr_url = arguments.get("pr_url")
            if tid is not None and pr_url:
                data, err = api_client.task_update(tid, pr_url=pr_url, status="WAIT_OWNER")
                result_text = f"Updated: {data}" if not err else f"Error: {err}"
                success = not err
            else:
                result_text = "Use Local Runner to create PR. Then call task_update with pr_url."

        elif name == "logs_get":
            if task_id is None:
                result_text = "Error: task_id or mission_id required"
            else:
                data, err = api_client.logs_get(task_id)
                if err:
                    result_text = f"Error: {err}"
                else:
                    result_text = _json_pretty(data)
                    success = True

        elif name == "health":
            ok, msg = api_client.health()
            result_text = f"ok={ok} {msg}"
            success = ok

        elif name == "gateway_catalog":
            data, err = api_client.gateway_catalog()
            if err:
                result_text = f"Error: {err}"
            else:
                result_text = _json_pretty(data)
                success = True

        else:
            result_text = f"Unknown tool: {name}"
    except Exception as e:
        logger.exception("Tool %s failed", name)
        result_text = f"Error: {e}"
    finally:
        api_client._current_request_id = None

    elapsed = int((time.perf_counter() - start) * 1000)
    _write_audit(name, task_id, success, elapsed, request_id)
    return result_text, success
