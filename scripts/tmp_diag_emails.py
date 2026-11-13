"""Diagnose contacts email column without printing values."""
from pathlib import Path

ENV = Path(r"C:\Users\X230\parser-news-bot.env")
CRED = Path(r"C:\Users\X230\parser-news-credentials.json")


def load_env(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> None:
    env = load_env(ENV)
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        str(CRED), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    data = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=env["GOOGLE_SHEET_ID"], range="'contacts'!A:H")
        .execute()
        .get("values", [])
    )
    hdr = [str(h).strip().lower() for h in data[0]]
    rows = data[1:]
    ei = hdr.index("email")
    vals = [str(r[ei]).strip() for r in rows if ei < len(r) and str(r[ei]).strip()]
    with_at = [v for v in vals if "@" in v]
    print("headers", hdr)
    print("nonempty", len(vals))
    print("with_at", len(with_at))
    print("distinct_all", len({v.lower() for v in vals}))
    print("distinct_at", len({v.lower() for v in with_at}))
    print("lens_first5", [len(v) for v in vals[:5]])
    print("has_at_first8", ["@" in v for v in vals[:8]])


if __name__ == "__main__":
    main()
