# app/runners/cursor_runner/sdk_runner.py — Cursor SDK executor with approve gates
"""Programmatic Cursor agent execution with policy-aware approval callback.

Uses cursor-sdk (Agent.prompt / Agent.create) when installed.
Critical actions are gated via approval_callback before / during execution.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from app.runners.cursor_runner.win_os_shim import ensure_windows_os_blocking_shim

logger = logging.getLogger(__name__)

ApprovalCallback = Callable[[dict[str, Any]], Awaitable[bool]]


class ApprovalRequired(Exception):
    """Raised when a critical tool call needs owner approval."""

    def __init__(self, action: str, details: dict[str, Any]):
        self.action = action
        self.details = details
        super().__init__(f"Approval required for: {action}")


def _critical_tokens() -> tuple[str, ...]:
    """Load critical action tokens; prefer shared-policy scopes when available."""
    default = (
        "git push", "git commit", "deploy", "publish", "rm -rf",
        "curl ", "npm publish", "gh pr merge", "write", "edit",
        "patch", "docker compose", "alembic",
    )
    try:
        from pathlib import Path as P
        import yaml

        root = P(__file__).resolve()
        for parent in root.parents:
            policy = parent / "packages" / "shared-policy" / "config" / "approval.yaml"
            if policy.exists():
                data = yaml.safe_load(policy.read_text(encoding="utf-8")) or {}
                scopes = [
                    a.get("scope", "").replace("_", " ")
                    for a in data.get("approval_required_actions", [])
                    if isinstance(a, dict)
                ]
                if scopes:
                    return tuple(scopes) + default
                break
    except Exception:
        pass
    return default


def _is_critical_action(action: str, details: dict[str, Any]) -> bool:
    """Policy gate: critical actions require owner approval."""
    action_lower = (action or "").lower()
    tokens = _critical_tokens()
    if any(t in action_lower for t in tokens):
        return True
    cmd = str(details.get("command") or details.get("tool_input") or "").lower()
    return any(t in cmd for t in tokens)


async def telegram_approval_callback(payload: dict[str, Any]) -> bool:
    """
    Default gate: deny critical actions unless CURSOR_AUTO_APPROVE=1
    or OWNER_APPROVED_ACTIONS contains the action token.
    Real Telegram approve is Owner HITL (bot buttons); this blocks unsafe auto-exec.
    """
    if os.getenv("CURSOR_AUTO_APPROVE", "").lower() in ("1", "true", "yes"):
        logger.warning("CURSOR_AUTO_APPROVE enabled — allowing: %s", payload.get("action"))
        return True
    approved = {
        x.strip().lower()
        for x in (os.getenv("OWNER_APPROVED_ACTIONS") or "").split(",")
        if x.strip()
    }
    action = str(payload.get("action") or "").lower()
    if action in approved or any(a in action for a in approved):
        return True
    logger.warning("Critical action pending owner approve: %s", payload)
    return False


async def run_cursor_sdk_agent(
    workspace_path: str,
    prompt: str,
    *,
    approval_callback: Optional[ApprovalCallback] = None,
    timeout_sec: int = 600,
    auto_review: bool = True,
) -> dict[str, Any]:
    """
    Run Cursor agent via SDK when available; fallback to CLI hint.
    approval_callback receives {action, details} and returns True to proceed.
    """
    workspace = Path(workspace_path)
    if not workspace.exists():
        return {"success": False, "error": f"Workspace not found: {workspace_path}", "mode": "none"}

    gate = approval_callback or telegram_approval_callback

    # Pre-gate only for clearly critical ops in the prompt text
    prompt_critical = ("git push", "git commit", "gh pr merge", "deploy", "rm -rf", "npm publish")
    pl = prompt.lower()
    if any(t in pl for t in prompt_critical):
        if not await gate({"action": "cursor_execute_critical", "command": prompt[:200]}):
            return {
                "success": False,
                "error": "Owner approval required before Cursor execution",
                "mode": "approval_gate",
                "blocked_action": "cursor_execute_critical",
            }

    sdk_result = await _try_cursor_sdk(
        str(workspace.resolve()),
        prompt,
        approval_callback=gate,
        timeout_sec=timeout_sec,
        auto_review=auto_review,
    )
    if sdk_result is not None:
        return sdk_result

    return await _fallback_cli_hint(str(workspace.resolve()), prompt)


async def _try_cursor_sdk(
    workspace_path: str,
    prompt: str,
    *,
    approval_callback: Optional[ApprovalCallback],
    timeout_sec: int,
    auto_review: bool,
) -> Optional[dict[str, Any]]:
    api_key = os.getenv("CURSOR_API_KEY") or os.getenv("CURSOR_SDK_API_KEY")
    if not api_key:
        logger.info("CURSOR_API_KEY not set; skipping SDK")
        return None

    # Windows: cursor-sdk may call Unix-only os.get_blocking / set_blocking.
    if ensure_windows_os_blocking_shim():
        logger.debug("Installed Windows os.get_blocking/set_blocking shim")

    Agent = None
    LocalAgentOptions = None
    AgentOptions = None
    try:
        from cursor_sdk import Agent, LocalAgentOptions  # type: ignore
        try:
            from cursor_sdk import AgentOptions  # type: ignore
        except ImportError:
            AgentOptions = None
    except ImportError:
        logger.info("cursor-sdk not installed; using fallback (pip install cursor-sdk)")
        return None

    async def _gate(action: str, details: dict[str, Any]) -> bool:
        if not _is_critical_action(action, details):
            return True
        if approval_callback is None:
            logger.warning("Critical action blocked (no approval_callback): %s", action)
            return False
        return await approval_callback({"action": action, **details})

    model = os.getenv("CURSOR_SDK_MODEL", "composer-2.5")

    def _run_sync() -> dict[str, Any]:
        opts_kw: dict[str, Any] = {
            "api_key": api_key,
            "model": model,
            "local": LocalAgentOptions(cwd=workspace_path),
        }
        # Prefer one-shot Agent.prompt when available
        if hasattr(Agent, "prompt"):
            try:
                if AgentOptions is not None:
                    result = Agent.prompt(prompt, AgentOptions(**opts_kw))
                else:
                    result = Agent.prompt(prompt, **opts_kw)
                status = getattr(result, "status", "ok")
                text = getattr(result, "result", None) or str(result)
                if status == "error":
                    return {"success": False, "error": text, "mode": "cursor_sdk"}
                return {"success": True, "mode": "cursor_sdk", "output": str(text)[:8000]}
            except TypeError:
                pass

        # Durable path: Agent.create + send (pre-gate already enforced above)
        with Agent.create(
            model=model,
            api_key=api_key,
            local=LocalAgentOptions(cwd=workspace_path),
        ) as agent:
            run = agent.send(prompt)
            chunks: list[str] = []
            if hasattr(run, "messages"):
                for message in run.messages():
                    msg_type = getattr(message, "type", "")
                    if msg_type == "assistant":
                        content = getattr(getattr(message, "message", None), "content", None) or []
                        for block in content:
                            if getattr(block, "type", "") == "text":
                                chunks.append(getattr(block, "text", ""))
                    tool = getattr(message, "tool_call", None)
                    if tool:
                        action = getattr(tool, "name", "tool_call")
                        details = {"tool_input": getattr(tool, "input", {})}
                        if _is_critical_action(action, details):
                            # Headless SDK cannot pause mid-tool; block and surface for Owner.
                            return {
                                "success": False,
                                "error": f"Owner approval required: {action}",
                                "mode": "cursor_sdk",
                                "blocked_action": action,
                            }
            if hasattr(run, "wait"):
                run.wait()
            output = "\n".join(chunks) if chunks else str(getattr(run, "result", run))
            return {"success": True, "mode": "cursor_sdk", "output": output[:8000]}

    try:
        return await asyncio.wait_for(asyncio.to_thread(_run_sync), timeout=timeout_sec)
    except asyncio.TimeoutError:
        return {"success": False, "error": "Cursor SDK timeout", "mode": "cursor_sdk"}
    except Exception as exc:
        logger.warning("Cursor SDK run failed: %s", exc)
        return {"success": False, "error": str(exc), "mode": "cursor_sdk"}


async def _fallback_cli_hint(workspace_path: str, prompt: str) -> dict[str, Any]:
    """When SDK unavailable, return instructions for manual/Cursor IDE execution."""
    brief = prompt[:500] + ("..." if len(prompt) > 500 else "")
    return {
        "success": True,
        "mode": "manual_hint",
        "output": (
            f"Cursor SDK not available. Install: pip install cursor-sdk\n"
            f"Set CURSOR_API_KEY. Open workspace {workspace_path} in Cursor and run:\n\n{brief}"
        ),
    }


def build_task_prompt(task_data: dict[str, Any], artifacts: Optional[list] = None) -> str:
    """Build executor prompt from task + artifacts."""
    lines = [
        "You are the MyWave coding executor. Apply changes per task handoffs.",
        f"Task ID: {task_data.get('id') or task_data.get('task_id')}",
        f"Summary: {task_data.get('summary', '')[:500]}",
        f"Owner text: {(task_data.get('owner_text') or '')[:1000]}",
    ]
    if artifacts:
        for art in artifacts[:5]:
            lines.append(f"Artifact: {art}")
    lines.append("Constraints: no auto-merge to main; run pytest before commit.")
    return "\n".join(lines)
