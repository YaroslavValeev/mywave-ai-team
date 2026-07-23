#!/usr/bin/env python3
# Phase 8.2: Единый process entrypoint для Molt HTTP service.
# Запуск: из корня репо PYTHONPATH=packages/shared-core:services python -m molt_http_service.run
# Или: python services/molt_http_service/run.py (при PYTHONPATH с shared-core и services).
from __future__ import annotations

import sys


def main() -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed; pip install uvicorn[standard]", file=sys.stderr)
        return 1
    try:
        from molt_http_service.app import app
        from molt_http_service.config import host, port
    except ImportError as e:
        print("Ensure PYTHONPATH includes packages/shared-core and services:", e, file=sys.stderr)
        return 1
    uvicorn.run(app, host=host(), port=port(), log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
