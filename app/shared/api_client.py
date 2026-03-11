# app/shared/api_client.py — HTTPS клиент для MCP/Runner
# base_url: MYWAVE_BASE_URL (fallback DASHBOARD_URL, fallback https://agm.mywavetreaning.ru)
# headers: X-API-Key: OWNER_API_KEY, X-Request-Id (для корреляции audit)

import logging
import os
import time
import uuid
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("MYWAVE_BASE_URL") or os.getenv("DASHBOARD_URL") or "https://agm.mywavetreaning.ru"
API_KEY = os.getenv("OWNER_API_KEY", "")
TIMEOUT = float(os.getenv("API_CLIENT_TIMEOUT", "30"))


def _headers(request_id: Optional[str] = None) -> dict:
    h = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    rid = request_id or _current_request_id
    if rid:
        h["X-Request-Id"] = rid
    return h


_current_request_id: Optional[str] = None


def _request(method: str, path: str, request_id: Optional[str] = None, **kwargs) -> tuple[int, Optional[dict | list], Optional[str]]:
    """Returns (status_code, json_body or None, error_message)."""
    url = BASE_URL.rstrip("/") + path
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.request(method, url, headers=_headers(request_id), **kwargs)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("API %s %s -> %d (%dms)", method, path, r.status_code, elapsed_ms)
        try:
            body = r.json()
        except Exception:
            body = None
        return r.status_code, body, None
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("API %s %s failed (%dms): %s", method, path, elapsed_ms, e)
        return -1, None, str(e)


def health() -> tuple[bool, str]:
    """GET /health. Returns (ok, message)."""
    url = BASE_URL.rstrip("/") + "/health"
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(url)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, str(e)


def task_create(domain: str, task_type: str, payload: Optional[dict] = None, criticality: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    """POST /api/tasks."""
    data = {"domain": domain, "task_type": task_type}
    if payload:
        data["payload"] = payload
    if criticality:
        data["criticality"] = criticality
    code, body, err = _request("POST", "/api/tasks", json=data)
    if err:
        return None, err
    if code == 200 or code == 201:
        return body, None
    return None, f"HTTP {code}: {body}"


def task_update(task_id: int, status: Optional[str] = None, pr_url: Optional[str] = None, commit_sha: Optional[str] = None, ci_url: Optional[str] = None, **kwargs) -> tuple[Optional[dict], Optional[str]]:
    """PATCH /api/tasks/{id}."""
    data = {}
    if status is not None:
        data["status"] = status
    if pr_url is not None:
        data["pr_url"] = pr_url
    if commit_sha is not None:
        data["commit_sha"] = commit_sha
    if ci_url is not None:
        data["ci_url"] = ci_url
    data.update(kwargs)
    code, body, err = _request("PATCH", f"/api/tasks/{task_id}", json=data)
    if err:
        return None, err
    if 200 <= code < 300:
        return body or {"ok": True}, None
    return None, f"HTTP {code}: {body}"


def task_get(task_id: int, raw: bool = False) -> tuple[Optional[dict], Optional[str]]:
    """GET /api/tasks/{id}."""
    path = f"/api/tasks/{task_id}"
    if raw:
        path += "?raw=1"
    code, body, err = _request("GET", path)
    if err:
        return None, err
    if code == 200:
        return body, None
    return None, f"HTTP {code}: {body}"


def artifacts_list(task_id: int) -> tuple[Optional[list], Optional[str]]:
    """GET /api/tasks/{id}/artifacts."""
    code, body, err = _request("GET", f"/api/tasks/{task_id}/artifacts")
    if err:
        return None, err
    if code == 200 and isinstance(body, dict) and "artifacts" in body:
        return body["artifacts"], None
    if code == 200 and isinstance(body, list):
        return body, None
    return None, f"HTTP {code}: {body}"


def artifacts_get(task_id: int, artifact_id: int) -> tuple[Optional[str], Optional[str]]:
    """GET /api/artifacts/{artifact_id}?task_id=..."""
    code, body, err = _request("GET", f"/api/artifacts/{artifact_id}?task_id={task_id}")
    if err:
        return None, err
    if code == 200 and isinstance(body, dict) and "content" in body:
        return body["content"], None
    return None, f"HTTP {code}: {body}"


def pipeline_run(task_id: int) -> tuple[Optional[dict], Optional[str]]:
    """POST /api/tasks/{id}/pipeline/run."""
    code, body, err = _request("POST", f"/api/tasks/{task_id}/pipeline/run")
    if err:
        return None, err
    if 200 <= code < 300:
        return body or {"ok": True}, None
    return None, f"HTTP {code}: {body}"


def audit_event(event_type: str, payload: dict, task_id: Optional[int] = None, request_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """POST /api/audit — записать событие (MCP tool invoke и т.п.)."""
    body = {"event_type": event_type, "payload": payload}
    if task_id is not None:
        body["task_id"] = task_id
    if request_id:
        body["request_id"] = request_id
    code, _, err = _request("POST", "/api/audit", request_id=request_id, json=body)
    if err:
        return False, err
    return 200 <= code < 300, None


def logs_get(task_id: int) -> tuple[Optional[str | list], Optional[str]]:
    """GET /api/tasks/{id}/logs."""
    code, body, err = _request("GET", f"/api/tasks/{task_id}/logs")
    if err:
        return None, err
    if code == 200:
        return body, None
    return None, f"HTTP {code}: {body}"
