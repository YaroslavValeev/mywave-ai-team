#!/usr/bin/env python3
"""Minimal live Cursor SDK smoke (Owner PC). Does not print the full API key.

Local runtime on Windows may fail (os.get_blocking). Falls back to cloud.

Usage:
  set CURSOR_API_KEY=...
  python scripts/smoke_cursor_sdk.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _preview(result: object) -> tuple[object, str]:
    status = getattr(result, "status", None)
    text = getattr(result, "result", None)
    if isinstance(result, dict):
        status = status or result.get("status")
        text = text if text is not None else (result.get("result") or result.get("output") or result.get("text"))
    return status, (str(text) if text is not None else "")[:500]


def main() -> int:
    key = (os.getenv("CURSOR_API_KEY") or os.getenv("CURSOR_SDK_API_KEY") or "").strip()
    if not key:
        print("FAIL: CURSOR_API_KEY not set", file=sys.stderr)
        return 1
    print(f"CURSOR_API_KEY set=True len={len(key)} prefix={key[:5]}...")

    # Shared helper (also used by sdk_runner before cursor_sdk import).
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.runners.cursor_runner.win_os_shim import ensure_windows_os_blocking_shim

    if ensure_windows_os_blocking_shim():
        print("note: installed Windows shim for os.get_blocking/set_blocking")

    try:
        from cursor_sdk import (
            Agent,
            AgentOptions,
            CloudAgentOptions,
            CloudRepository,
            LocalAgentOptions,
        )
    except ImportError as exc:
        print(f"FAIL: cursor_sdk import: {exc}", file=sys.stderr)
        print("hint: pip install cursor-sdk", file=sys.stderr)
        return 1

    cwd = str(Path(__file__).resolve().parents[1])
    prompt = (
        "Reply with exactly one short line: SDK_SMOKE_OK. "
        "Do not modify any files. Do not open PRs."
    )
    print(f"cwd={cwd}")

    # 1) Local first
    print("try: Agent.prompt local...")
    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=key,
                model="composer-2.5",
                local=LocalAgentOptions(cwd=cwd),
            ),
        )
        status, text_s = _preview(result)
        print(f"local status={status}")
        print(f"local result_preview={text_s!r}")
        print("OK: Cursor SDK live smoke (local)")
        return 0
    except Exception as exc:
        print(f"local failed: {type(exc).__name__}: {exc}")

    # 2) Cloud fallback (no auto PR)
    repo = os.getenv("CURSOR_SDK_SMOKE_REPO", "https://github.com/YaroslavValeev/mywave-ai-team")
    ref = os.getenv("CURSOR_SDK_SMOKE_REF", "main")
    print(f"try: Agent.prompt cloud repo={repo} ref={ref}...")
    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=key,
                model="composer-2.5",
                cloud=CloudAgentOptions(
                    repos=[CloudRepository(url=repo, starting_ref=ref)],
                    auto_create_pr=False,
                    skip_reviewer_request=True,
                ),
            ),
        )
        status, text_s = _preview(result)
        print(f"cloud status={status}")
        print(f"cloud result_preview={text_s!r}")
        print("OK: Cursor SDK live smoke (cloud)")
        return 0
    except Exception as exc:
        print(f"FAIL: cloud Agent.prompt: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
