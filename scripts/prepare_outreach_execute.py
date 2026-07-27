#!/usr/bin/env python3
"""Prepare or complete minimal outreach EXECUTE pack (no auto-send).

Examples (on RU host or inside app container):

  python scripts/prepare_outreach_execute.py --task-id 33
  python scripts/prepare_outreach_execute.py --task-id 33 --mark-done
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _ensure_repo_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def main() -> int:
    _ensure_repo_root()
    parser = argparse.ArgumentParser(description="Minimal outreach EXECUTE pack helper")
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument(
        "--mark-done",
        action="store_true",
        help="After send_log filled: set task status DONE (does not send mail)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Prepare pack even if task type is not content/MEDIA",
    )
    args = parser.parse_args()

    # Prefer same DB as app
    from app.storage.repositories import TaskRepository, get_session_factory
    from app.orchestrator.execution_pack import (
        prepare_outreach_execution_pack,
        task_wants_outreach_execute,
    )

    Session = get_session_factory()
    with Session() as session:
        repo = TaskRepository(session)
        task = repo.get_task(args.task_id)
        if not task:
            print(f"ERROR: task {args.task_id} not found", file=sys.stderr)
            return 1

        if args.mark_done:
            repo.update_task(args.task_id, status="DONE")
            ba = dict(task.business_action_json or {})
            ba["execution_completed_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
            repo.update_task(args.task_id, business_action_json=ba)
            try:
                repo.add_audit_event(
                    "EXECUTION_MARKED_DONE",
                    task_id=args.task_id,
                    payload={"source": "prepare_outreach_execute_script"},
                )
            except Exception:
                pass
            print(f"OK: task #{args.task_id} → DONE")
            return 0

        if not args.force and not task_wants_outreach_execute(task):
            print(
                f"SKIP: task #{args.task_id} type={task.task_type!r} "
                "does not look like outreach (use --force to write pack anyway)",
                file=sys.stderr,
            )
            return 2

        result = prepare_outreach_execution_pack(
            repo, args.task_id, source="cli_prepare_outreach_execute"
        )
        if not result.get("ok"):
            print(f"ERROR: {result}", file=sys.stderr)
            return 1
        # Align status for manual prepare after approve
        if getattr(task, "status", None) in {"WAIT_OWNER", "DONE", "NEED_INFO"}:
            repo.update_task(args.task_id, status="EXECUTION_READY")
        print("OK: EXECUTE pack ready")
        print(f"  pack: {result.get('pack_path')}")
        print(f"  message: {result.get('message_path')}")
        print(f"  contacts: {result.get('contacts_path') or '(none yet)'}")
        print("  auto_send: false")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
