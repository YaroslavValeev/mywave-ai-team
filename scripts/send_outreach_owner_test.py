#!/usr/bin/env python3
"""Send outreach draft as a single TEST message to Owner Telegram only.

Hard gates:
- destination = OWNER_CHAT_ID only (never contact CSV)
- requires --i-confirm-owner-test
- does not mark task DONE

Example (RU container):

  docker compose exec app python scripts/send_outreach_owner_test.py \\
    --task-id 33 --i-confirm-owner-test
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    parser = argparse.ArgumentParser(description="Owner-TG test send for outreach draft")
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument(
        "--i-confirm-owner-test",
        action="store_true",
        help="Required: confirm single test to OWNER_CHAT_ID only",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    if not args.i_confirm_owner_test:
        print(
            "REFUSED: pass --i-confirm-owner-test (sends ONLY to Owner TG, never CSV list)",
            file=sys.stderr,
        )
        return 2

    artifacts = args.artifacts_dir or (root / "app" / "artifacts")
    exe = artifacts / "tasks" / f"task_{args.task_id}" / "execution"
    msg_path = exe / "message_to_send.txt"
    if not msg_path.is_file():
        print(f"ERROR: missing {msg_path}", file=sys.stderr)
        return 1

    body = msg_path.read_text(encoding="utf-8").strip()
    if not body:
        print("ERROR: message_to_send.txt is empty", file=sys.stderr)
        return 1

    text = (
        f"🧪 TEST outreach — task #{args.task_id}\n"
        f"(только ваш Telegram / Owner; это не массовая рассылка)\n\n"
        f"{body}"
    )

    from app.bot.notify import send_owner_message
    from app.config import get_telegram_config
    import os

    cfg = get_telegram_config()
    owner = cfg.get("owner_chat_id") or os.getenv("OWNER_CHAT_ID")
    if not owner:
        print("ERROR: OWNER_CHAT_ID not configured", file=sys.stderr)
        return 1

    ok = asyncio.run(send_owner_message(text, parse_mode=None))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_path = exe / "send_log.md"
    prev = log_path.read_text(encoding="utf-8") if log_path.is_file() else "# send_log\n\n"
    section = (
        f"\n## {now} — Owner TG TEST\n\n"
        f"- recipients_sent: **{'1' if ok else '0'}** (Owner only)\n"
        f"- channel: telegram_owner_dm\n"
        f"- target: OWNER_CHAT_ID (not CSV)\n"
        f"- result: {'ok' if ok else 'FAIL'}\n"
        f"- mass_send: false\n"
    )
    log_path.write_text(prev.rstrip() + "\n" + section + "\n", encoding="utf-8")

    if not ok:
        print("FAIL: Telegram send to Owner failed (check bot token / proxy / OWNER_CHAT_ID)", file=sys.stderr)
        return 1

    print(f"OK: test message sent to Owner TG (task #{args.task_id})")
    print("  mass_send: false")
    print("  recipients_sent: 1 (owner only)")
    print(f"  send_log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
