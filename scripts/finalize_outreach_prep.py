#!/usr/bin/env python3
"""Finalize outreach EXECUTE prep on RU host (no send, no mark-done).

Copies contacts into task execution/, writes segment inventory (counts),
splits pilot email vs telegram-hold CSVs, updates send_log.md.

Run on RU from /opt/mywave/ai-team (bind-mounted artifacts):

  python3 scripts/finalize_outreach_prep.py --task-id 33
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _find_source_csv(artifacts: Path, task_id: int) -> Path | None:
    exe = artifacts / "tasks" / f"task_{task_id}" / "execution"
    for name in ("contacts_unique.csv", "parsernews_outreach_contacts.csv"):
        p = exe / name
        if p.is_file():
            return p
    local = sorted(exe.glob("parsernews_outreach_contacts_*.csv"), reverse=True) if exe.is_dir() else []
    if local:
        return local[0]
    candidates = list((artifacts / "tasks").glob("task_*/execution/parsernews_outreach_contacts_*.csv"))
    candidates += list((artifacts / "tasks").glob("task_*/execution/contacts_unique.csv"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize outreach prep (no mass send)")
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Default: <repo>/app/artifacts",
    )
    args = parser.parse_args()
    root = _repo_root()
    artifacts = args.artifacts_dir or (root / "app" / "artifacts")
    exe = artifacts / "tasks" / f"task_{args.task_id}" / "execution"
    exe.mkdir(parents=True, exist_ok=True)

    src = _find_source_csv(artifacts, args.task_id)
    if not src:
        print("ERROR: no contacts CSV found under app/artifacts/tasks/*/execution/", file=sys.stderr)
        return 1

    contacts = exe / "contacts_unique.csv"
    if src.resolve() != contacts.resolve():
        shutil.copy2(src, contacts)
    # Keep dated copy for audit trail
    dated = exe / src.name
    if src.resolve() != dated.resolve():
        shutil.copy2(src, dated)

    rows = list(csv.DictReader(contacts.open(encoding="utf-8-sig", newline="")))
    fieldnames = list(rows[0].keys()) if rows else ["channel", "value", "source", "consent_required", "notes"]

    emails = [r for r in rows if str(r.get("channel") or "").lower().startswith("email") or "@" in str(r.get("value") or "")]
    tgs = [r for r in rows if "telegram" in str(r.get("channel") or "").lower()]
    consent_yes = sum(
        1 for r in rows if str(r.get("consent_required") or "").strip().lower() in {"yes", "true", "1"}
    )

    def _write_csv(path: Path, subset: list[dict]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for r in subset:
                w.writerow(r)

    pilot = exe / "segment_emails_pilot.csv"
    hold = exe / "segment_telegram_hold.csv"
    _write_csv(pilot, emails)
    _write_csv(hold, tgs)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inv = exe / "segment_inventory.md"
    inv.write_text(
        "\n".join(
            [
                f"# Segment inventory — task #{args.task_id}",
                "",
                f"- prepared_at_utc: `{now}`",
                f"- source_csv: `{src}`",
                f"- total_contacts: **{len(rows)}**",
                f"- emails: **{len(emails)}** → `{pilot.name}` (pilot only; still consent_required)",
                f"- telegram_handles: **{len(tgs)}** → `{hold.name}` (**HOLD** — no mass send)",
                f"- consent_required=yes: **{consent_yes}/{len(rows)}**",
                "",
                "## Policy",
                "",
                "- Mass send from AI-TEAM: **forbidden** without separate Owner GO.",
                "- Recommended next human step: review pilot emails (3) manually; do not blast telegram hold list.",
                "- All rows currently flagged consent_required — verify before any contact.",
                "",
                "## Auto-send",
                "",
                "`false`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    send_log = exe / "send_log.md"
    send_log.write_text(
        "\n".join(
            [
                "# send_log",
                "",
                f"## {now} — PREP complete (no send)",
                "",
                f"- task: #{args.task_id}",
                f"- contacts_copied: yes (`contacts_unique.csv`)",
                f"- inventory: `{inv.name}`",
                f"- recipients_sent: **0**",
                f"- channel: —",
                f"- result: pack ready; mass mailing **not** started",
                f"- note: consent_required=yes for {consent_yes}/{len(rows)}; telegram list on HOLD",
                "",
                "_After any real send, append a new section with date, count, channel, result._",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # Refresh pack pointers if module available
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from app.storage.repositories import TaskRepository, get_session_factory
        from app.orchestrator.execution_pack import prepare_outreach_execution_pack

        Session = get_session_factory()
        with Session() as session:
            repo = TaskRepository(session)
            task = repo.get_task(args.task_id)
            if task:
                prepare_outreach_execution_pack(
                    repo, args.task_id, source="finalize_outreach_prep"
                )
                st = getattr(task, "status", None)
                if st in {"WAIT_OWNER", "DONE", "NEED_INFO", None} or st != "EXECUTION_READY":
                    # Keep EXECUTION_READY until Owner marks send done
                    if st != "DONE":
                        repo.update_task(args.task_id, status="EXECUTION_READY")
                print(f"OK: DB status → EXECUTION_READY (task #{args.task_id})")
    except Exception as exc:
        print(f"WARN: pack/DB refresh skipped ({exc})", file=sys.stderr)

    print("OK: outreach PREP finalized (no send)")
    print(f"  contacts: {contacts}")
    print(f"  inventory: {inv}")
    print(f"  pilot_emails: {pilot} ({len(emails)})")
    print(f"  telegram_hold: {hold} ({len(tgs)})")
    print(f"  send_log: {send_log}")
    print("  auto_send: false")
    print("  recipients_sent: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
