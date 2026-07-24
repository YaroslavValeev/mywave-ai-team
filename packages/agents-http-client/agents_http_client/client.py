"""Minimal Control API client — urllib only (no extra deps)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


class AgentsControlError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class AgentsControlClient:
    """Client for /api/* on Agents dashboard (X-API-Key auth)."""

    def __init__(self, base_url: str, api_key: str, timeout_sec: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_sec = timeout_sec

    @classmethod
    def from_env(cls) -> "AgentsControlClient":
        base = (
            os.getenv("AGENTS_CONTROL_API_URL")
            or os.getenv("DASHBOARD_URL")
            or "http://127.0.0.1:8088"
        ).rstrip("/")
        key = os.getenv("AGENTS_API_KEY") or os.getenv("OWNER_API_KEY") or ""
        if not key:
            raise AgentsControlError(
                "AGENTS_API_KEY or OWNER_API_KEY must be set for Control API client"
            )
        timeout = float(os.getenv("AGENTS_HTTP_TIMEOUT_SEC", "30"))
        return cls(base_url=base, api_key=key, timeout_sec=timeout)

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            err_body: Any
            try:
                err_body = json.loads(exc.read().decode("utf-8"))
            except Exception:
                err_body = None
            raise AgentsControlError(
                f"{method} {path} failed: HTTP {exc.code}",
                status=exc.code,
                body=err_body,
            ) from exc
        except urllib.error.URLError as exc:
            raise AgentsControlError(f"{method} {path} failed: {exc}") from exc

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/system/health")

    def list_tasks(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/api/tasks")
        return list(result or [])

    def get_task(self, task_id: int | str) -> dict[str, Any]:
        return self._request("GET", f"/api/tasks/{task_id}")

    def create_task(
        self,
        owner_text: Optional[str] = None,
        *,
        domain: str = "PRODUCT_DEV",
        task_type: str = "general",
        payload: Optional[dict[str, Any]] = None,
        criticality: str = "MEDIUM",
        auto_run: bool = False,
    ) -> dict[str, Any]:
        if owner_text:
            body: dict[str, Any] = {"owner_text": owner_text}
        else:
            body = {
                "domain": domain,
                "task_type": task_type,
                "payload": payload or {},
                "criticality": criticality,
            }
        if auto_run:
            body["auto_run"] = True
        created = self._request("POST", "/api/tasks", body)
        if auto_run and isinstance(created, dict):
            tid = created.get("id") or created.get("task_id")
            if tid is not None and created.get("status") == "NEW":
                # Fallback when API ignores auto_run (older deploy)
                piped = self.run_pipeline(tid)
                if isinstance(piped, dict) and piped.get("status"):
                    created = {**created, **piped, "id": tid, "mission_id": tid}
        return created

    def run_pipeline(self, task_id: int | str) -> dict[str, Any]:
        return self._request("POST", f"/api/tasks/{task_id}/pipeline/run")

    def approve(self, task_id: int | str, note: str = "") -> dict[str, Any]:
        """POST /api/tasks/{id}/approve. Idempotent if already DONE / APPROVED_WAIT_MERGE."""
        try:
            return self._request(
                "POST", f"/api/tasks/{task_id}/approve", {"note": note} if note else {}
            )
        except AgentsControlError as exc:
            if getattr(exc, "status", None) != 409:
                raise
            # Already decided / not WAIT_OWNER — treat terminal success as OK
            try:
                task = self.get_task(task_id)
            except AgentsControlError:
                raise exc from None
            status = str(task.get("status") or "")
            if status in {"DONE", "APPROVED_WAIT_MERGE", "ARCHIVED"}:
                return {
                    "id": task.get("id", task_id),
                    "status": status,
                    "decision": "approve",
                    "idempotent": True,
                    "detail": "already_terminal",
                }
            raise

    def rework(self, task_id: int | str, note: str = "") -> dict[str, Any]:
        return self._request(
            "POST", f"/api/tasks/{task_id}/rework", {"note": note} if note else {}
        )

    def clarify(self, task_id: int | str, note: str = "") -> dict[str, Any]:
        return self._request(
            "POST", f"/api/tasks/{task_id}/clarify", {"note": note} if note else {}
        )

    def mark_merged(self, task_id: int | str) -> dict[str, Any]:
        """POST /api/tasks/{id}/merged — Owner confirms manual PR merge."""
        return self._request("POST", f"/api/tasks/{task_id}/merged")

    def list_runs(self, task_id: int | str) -> Any:
        return self._request("GET", f"/api/tasks/{task_id}/runs")

    def list_execution_events(self, task_id: int | str) -> Any:
        return self._request("GET", f"/api/tasks/{task_id}/execution-events")

    def list_events(
        self,
        *,
        task_id: Optional[int | str] = None,
        mission_id: Optional[int | str] = None,
    ) -> Any:
        q = []
        if task_id is not None:
            q.append(f"task_id={task_id}")
        if mission_id is not None:
            q.append(f"mission_id={mission_id}")
        suffix = ("?" + "&".join(q)) if q else ""
        return self._request("GET", f"/api/events{suffix}")
