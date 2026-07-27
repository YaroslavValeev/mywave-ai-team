#!/usr/bin/env bash
# One-shot PREP for task 33 on RU — no mass send.
# Paste on RU: bash /tmp/finalize_task33_prep.sh   OR run lines manually.
set -euo pipefail
cd /opt/mywave/ai-team
N=33
EXE="app/artifacts/tasks/task_${N}/execution"
SRC="app/artifacts/tasks/task_32/execution/parsernews_outreach_contacts_20260727.csv"
mkdir -p "$EXE"
cp -f "$SRC" "$EXE/contacts_unique.csv"
cp -f "$SRC" "$EXE/parsernews_outreach_contacts_20260727.csv"

python3 - <<'PY'
import csv
from datetime import datetime, timezone
from pathlib import Path

exe = Path("app/artifacts/tasks/task_33/execution")
contacts = exe / "contacts_unique.csv"
rows = list(csv.DictReader(contacts.open(encoding="utf-8-sig", newline="")))
fields = list(rows[0].keys()) if rows else ["channel", "value", "source", "consent_required", "notes"]
emails = [r for r in rows if str(r.get("channel") or "").lower().startswith("email") or "@" in str(r.get("value") or "")]
tgs = [r for r in rows if "telegram" in str(r.get("channel") or "").lower()]
consent_yes = sum(1 for r in rows if str(r.get("consent_required") or "").strip().lower() in {"yes", "true", "1"})
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def write_csv(path, subset):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in subset:
            w.writerow(r)

write_csv(exe / "segment_emails_pilot.csv", emails)
write_csv(exe / "segment_telegram_hold.csv", tgs)
(exe / "segment_inventory.md").write_text(
    f"""# Segment inventory — task #33

- prepared_at_utc: `{now}`
- total_contacts: **{len(rows)}**
- emails: **{len(emails)}** → `segment_emails_pilot.csv` (pilot; consent still required)
- telegram_handles: **{len(tgs)}** → `segment_telegram_hold.csv` (**HOLD**)
- consent_required=yes: **{consent_yes}/{len(rows)}**

## Policy
- Mass send from AI-TEAM: **forbidden** without separate Owner GO.
- Recommended: review pilot emails only; telegram list on HOLD.
- Auto-send: `false`
""",
    encoding="utf-8",
)
(exe / "send_log.md").write_text(
    f"""# send_log

## {now} — PREP complete (no send)

- task: #33
- contacts_copied: yes (`contacts_unique.csv`)
- inventory: `segment_inventory.md`
- recipients_sent: **0**
- channel: —
- result: pack ready; mass mailing **not** started
- note: consent_required=yes for {consent_yes}/{len(rows)}; telegram HOLD

_After any real send, append a new section with date, count, channel, result._
""",
    encoding="utf-8",
)
print(f"OK prep: total={len(rows)} emails={len(emails)} tg_hold={len(tgs)} sent=0")
PY

# Refresh EXECUTE_PACK via existing script (already on main)
docker compose exec -T app python scripts/prepare_outreach_execute.py --task-id 33

echo "---- files ----"
ls -la "$EXE"
echo "---- inventory ----"
cat "$EXE/segment_inventory.md"
echo "DONE PREP (no send, no mark-done)"
