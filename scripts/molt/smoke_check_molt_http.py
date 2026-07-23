#!/usr/bin/env python3
# Phase 8.2: Smoke-check Molt HTTP service — /health, /ready, один boundary call.
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    base = os.getenv("MOLT_HTTP_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    timeout = 10
    errors = []

    # GET /health
    try:
        with urlopen(f"{base}/health", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            if data.get("status") != "ok":
                errors.append(f"/health returned status={data.get('status')}")
    except (URLError, HTTPError, OSError) as e:
        errors.append(f"/health failed: {e}")
    except Exception as e:
        errors.append(f"/health error: {e}")

    # GET /ready
    try:
        with urlopen(f"{base}/ready", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            if data.get("status") != "ready":
                errors.append(f"/ready not ready: {data.get('reason', data)}")
    except (URLError, HTTPError, OSError) as e:
        errors.append(f"/ready failed: {e}")
    except Exception as e:
        errors.append(f"/ready error: {e}")

    # POST /executions (minimal; может вернуть accepted=false если task не зарегистрирован — это ок для smoke)
    try:
        body = json.dumps({"canonical_task_id": "smoke-check-dummy-task"}).encode("utf-8")
        req = Request(
            f"{base}/executions",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            if not isinstance(data, dict):
                errors.append("/executions returned non-dict")
            elif "accepted" not in data:
                errors.append("/executions response missing 'accepted'")
    except (URLError, HTTPError, OSError) as e:
        errors.append(f"/executions failed: {e}")
    except Exception as e:
        errors.append(f"/executions error: {e}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print("smoke_check OK: health, ready, executions endpoint reachable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
