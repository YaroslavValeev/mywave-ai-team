#!/usr/bin/env python3
"""Smoke: Agents Control API health + create + list (не требует approve).

Usage:
  export AGENTS_CONTROL_API_URL=https://agm.mywavewake.ru
  export AGENTS_API_KEY=...   # or OWNER_API_KEY
  python scripts/smoke_agents_control.py

  # только health:
  python scripts/smoke_agents_control.py --health-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "packages" / "agents-http-client"
if str(CLIENT) not in sys.path:
    sys.path.insert(0, str(CLIENT))

from agents_http_client import AgentsControlClient, AgentsControlError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke Agents Control API")
    parser.add_argument("--health-only", action="store_true")
    parser.add_argument(
        "--text",
        default="#TASK smoke_agents_control from scripts",
        help="owner_text for create",
    )
    args = parser.parse_args()

    try:
        client = AgentsControlClient.from_env()
    except AgentsControlError as exc:
        print(f"FAIL config: {exc}", file=sys.stderr)
        return 2

    print(f"URL={client.base_url}")
    try:
        health = client.health()
    except AgentsControlError as exc:
        print(f"FAIL health: {exc}", file=sys.stderr)
        return 1
    print("health:", json.dumps(health, ensure_ascii=False)[:500])
    if health.get("status") != "ok":
        return 1
    if args.health_only:
        print("OK health-only")
        return 0

    try:
        task = client.create_task(owner_text=args.text)
        print("created:", json.dumps(task, ensure_ascii=False)[:800])
        tid = task.get("id") or task.get("task_id")
        if tid is not None:
            detail = client.get_task(tid)
            print("get_task:", json.dumps(detail, ensure_ascii=False)[:500])
    except AgentsControlError as exc:
        print(f"FAIL create/get: {exc} body={exc.body}", file=sys.stderr)
        return 1

    print("OK smoke_agents_control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
