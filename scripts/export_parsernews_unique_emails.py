"""Export outreach contacts from ParserNews Google Sheet.

Outputs CSV on Owner PC. Prints COUNTS only (no PII to stdout).
- Real emails: values containing @
- Telegram handles: username column + email-column values without @
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ENV = Path(r"C:\Users\X230\parser-news-bot.env")
CRED = Path(r"C:\Users\X230\parser-news-credentials.json")
OUT_DIR = Path(r"C:\Users\X230\Downloads")


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    env = load_env(ENV)
    sheet_id = env.get("GOOGLE_SHEET_ID")
    if not sheet_id or not CRED.exists():
        print("missing sheet_id or credentials", file=sys.stderr)
        return 1

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        str(CRED), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    data = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range="'contacts'!A:H")
        .execute()
        .get("values", [])
    )
    if not data:
        print("empty sheet")
        return 1

    hdr = [str(h).strip().lower() for h in data[0]]
    rows = data[1:]
    idx = {name: hdr.index(name) for name in hdr}

    emails: dict[str, str] = {}
    handles: dict[str, str] = {}

    def cell(r: list, name: str) -> str:
        i = idx.get(name)
        if i is None or i >= len(r):
            return ""
        return str(r[i]).strip()

    for r in rows:
        source = cell(r, "source")
        email = cell(r, "email")
        username = cell(r, "username")
        if email:
            if "@" in email:
                key = email.lower()
                emails.setdefault(key, source)
            else:
                # Often a TG handle stored in email column
                h = email.lstrip("@")
                if h:
                    handles.setdefault(h.lower(), source)
        if username:
            handles.setdefault(username.lstrip("@").lower(), source)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = OUT_DIR / f"parsernews_outreach_contacts_{stamp}.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["channel", "value", "source", "consent_required", "notes"])
        for email, src in sorted(emails.items()):
            w.writerow(["email", email, src, "yes", "ParserNews contacts"])
        for handle, src in sorted(handles.items()):
            w.writerow(["telegram_username", handle, src, "yes", "ParserNews contacts/handle"])

    meta_path = OUT_DIR / f"parsernews_outreach_contacts_{stamp}.meta.txt"
    meta_path.write_text(
        "\n".join(
            [
                f"rows_scanned={len(rows)}",
                f"unique_emails={len(emails)}",
                f"unique_telegram_handles={len(handles)}",
                f"csv={out_path}",
                f"generated_utc={datetime.now(timezone.utc).isoformat()}",
                "Note: most 'email' cells historically lack @ — treated as telegram handles.",
                "PII: do not commit to git.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"OK unique_emails={len(emails)} unique_telegram_handles={len(handles)} "
        f"csv={out_path.name} meta={meta_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
