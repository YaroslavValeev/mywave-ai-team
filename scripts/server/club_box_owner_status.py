"""Root-only local status client. Never prints or accepts the credential in argv."""

import json
import stat
import urllib.error
import urllib.request
from pathlib import Path


def main():
    folder = Path(__file__).resolve().parent
    path = folder / "owner.env"
    for entry in (folder, path):
        info = entry.lstat()
        if entry.is_symlink() or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077:
            raise RuntimeError("Owner credential permissions are unsafe")
    name, value = path.read_text().strip().split("=", 1)
    if name != "WORKSPACE_KEY_CLUB_BOX_OWNER" or len(value) != 64:
        raise RuntimeError("Unexpected credential format")
    request = urllib.request.Request(
        "http://127.0.0.1:8088/api/workspaces/1/projects/2/tasks",
        headers={"X-API-Key": value},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        tasks = json.load(response)
    if not isinstance(tasks, list):
        raise RuntimeError("Unexpected API response")
    print(
        json.dumps(
            {
                "access_verified": True,
                "workspace_id": 1,
                "project_id": 2,
                "task_count": len(tasks),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        print("ACCESS_CHECK_FAILED: HTTP", error.code)
        raise SystemExit(1)
    except Exception as error:
        print(
            "ACCESS_CHECK_FAILED:",
            str(error) if isinstance(error, RuntimeError) else type(error).__name__,
        )
        raise SystemExit(1)
