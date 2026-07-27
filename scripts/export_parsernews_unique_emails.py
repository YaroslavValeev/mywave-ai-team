"""Export unique emails from ParserNews Google Sheet contacts tab.

Writes CSV locally. Does NOT print email values to stdout (COUNT + path only).
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
    try:
        email_i = hdr.index("email")
        source_i = hdr.index("source") if "source" in hdr else None
    except ValueError:
        print("no email column", hdr)
        return 1

    # unique by normalized email; keep first source
    uniq: dict[str, str] = {}
    for r in rows:
        if email_i >= len(r):
            continue
        email = str(r[email_i]).strip()
        if not email or "@" not in email:
            continue
        key = email.lower()
        if key in uniq:
            continue
        src = str(r[source_i]).strip() if source_i is not None and source_i < len(r) else ""
        uniq[key] = src

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = OUT_DIR / f"parsernews_unique_emails_{stamp}.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["email", "source", "consent_required", "notes"])
        for email, src in sorted(uniq.items()):
            w.writerow([email, src, "yes", "from ParserNews contacts; review before send"])

    meta_path = OUT_DIR / f"parsernews_unique_emails_{stamp}.meta.txt"
    meta_path.write_text(
        "\n".join(
            [
                f"rows_scanned={len(rows)}",
                f"unique_emails={len(uniq)}",
                f"csv={out_path}",
                f"generated_utc={datetime.now(timezone.utc).isoformat()}",
                "PII: do not commit to git; Owner-only transfer to RU artifacts if needed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"OK unique_emails={len(uniq)} csv={out_path.name} meta={meta_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
