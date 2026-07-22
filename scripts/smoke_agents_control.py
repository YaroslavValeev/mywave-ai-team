#!/usr/bin/env python3
"""Smoke: Agents Control API health / create / pipeline / approve.

Usage (on RU or PC, with .env sourced or env vars set):
  python3 scripts/smoke_agents_control.py --health-only
  python3 scripts/smoke_agents_control.py --text "#TASK smoke"
  python3 scripts/smoke_agents_control.py --pipeline 4
  python3 scripts/smoke_agents_control.py --approve 4 --note "ok"
  python3 scripts/smoke_agents_control.py --full --text "#TASK smoke B full"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "packages" / "agents-http-client"
if str(CLIENT) not in sys.path:
    sys.path.insert(0, str(CLIENT))

from agents_http_client import AgentsControlClient, AgentsControlError  # noqa: E402


def _pp(label: str, data: object, limit: int = 800) -> None:
    print(f"{label}:", json.dumps(data, ensure_ascii=False)[:limit])


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke Agents Control API")
    parser.add_argument("--health-only", action="store_true")
    parser.add_argument("--full", action="store_true", help="create → pipeline → wait WAIT_OWNER")
    parser.add_argument("--pipeline", type=int, metavar="TASK_ID", help="POST pipeline/run")
    parser.add_argument("--approve", type=int, metavar="TASK_ID", help="POST approve")
    parser.add_argument("--note", default="smoke approve", help="approve note")
    parser.add_argument("--wait-sec", type=int, default=180, help="max wait for WAIT_OWNER in --full")
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
    _pp("health", health, 500)
    if health.get("status") != "ok":
        return 1
    if args.health_only:
        print("OK health-only")
        return 0

    if args.pipeline is not None:
        try:
            out = client.run_pipeline(args.pipeline)
            _pp("pipeline", out)
            detail = client.get_task(args.pipeline)
            _pp("get_task", detail, 500)
        except AgentsControlError as exc:
            print(f"FAIL pipeline: {exc} body={exc.body}", file=sys.stderr)
            return 1
        print("OK pipeline")
        return 0

    if args.approve is not None:
        try:
            out = client.approve(args.approve, note=args.note)
            _pp("approve", out)
        except AgentsControlError as exc:
            print(f"FAIL approve: {exc} body={exc.body}", file=sys.stderr)
            return 1
        print("OK approve")
        return 0

    try:
        task = client.create_task(owner_text=args.text)
        _pp("created", task)
        tid = task.get("id") or task.get("task_id")
        if tid is None:
            print("FAIL: no task id in create response", file=sys.stderr)
            return 1
        detail = client.get_task(tid)
        _pp("get_task", detail, 500)
    except AgentsControlError as exc:
        print(f"FAIL create/get: {exc} body={exc.body}", file=sys.stderr)
        return 1

    if not args.full:
        print("OK smoke_agents_control (create only)")
        return 0

    try:
        _pp("pipeline", client.run_pipeline(tid))
    except AgentsControlError as exc:
        print(f"FAIL pipeline: {exc} body={exc.body}", file=sys.stderr)
        return 1

    deadline = time.time() + max(30, args.wait_sec)
    status = None
    while time.time() < deadline:
        detail = client.get_task(tid)
        status = detail.get("status")
        print(f"status={status}")
        if status in ("WAIT_OWNER", "DONE", "APPROVED", "EXECUTE", "MERGED"):
            break
        time.sleep(5)
    _pp("final", detail, 600)
    if status == "WAIT_OWNER":
        print("OK full → WAIT_OWNER (approve via Telegram or --approve)")
        return 0
    print(f"WARN full ended with status={status}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
